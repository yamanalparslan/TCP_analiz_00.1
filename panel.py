import streamlit as st
import time
import pandas as pd
from datetime import datetime
from pymodbus.client import ModbusTcpClient
import plotly.graph_objects as go
import veritabani
import utils
from styles import inject_glossy_css, section_header, status_bar, kpi_row
from auth import check_auth, logout_button

# --- SAYFA AYARLARI ---
st.set_page_config(
    page_title="Solar Monitor",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)

# --- AUTH KONTROLÜ ---
if not check_auth():
    st.stop()

# DB Başlat
veritabani.init_db()

# --- GLOSSY CSS TEMA ---
inject_glossy_css()
logout_button()

# --- YARDIMCI FONKSİYONLAR ---

@st.cache_resource
def get_modbus_client(ip, port):
    return ModbusTcpClient(ip, port=port, timeout=2)

def to_signed16(value: int) -> int:
    """Modbus unsigned 16-bit register'ı signed int'e çevirir."""
    return value - 65536 if value > 32767 else value

def read_device_with_retry(client, slave_id, config, max_retries=3):
    last_error = None

    for attempt in range(max_retries):
        try:
            if not client.connected:
                client.connect()
                if not client.connected:
                    last_error = "Bağlantı kurulamadı"
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return None, last_error

            # 1. Güç
            r_guc = client.read_holding_registers(address=config['guc_addr'], count=1, slave=slave_id)
            if r_guc.isError():
                last_error = f"Güç okunamadı (ID:{slave_id})"
                if attempt < max_retries - 1:
                    time.sleep(0.3)
                    try:
                        client.close()
                    except Exception:
                        pass
                    continue
                return None, last_error
            val_guc = r_guc.registers[0] * config['guc_scale']  # Güç negatif olmaz, signed gerekmez
            time.sleep(0.05)  # ← Okumalar arası küçük bekleme

            # 2. Voltaj — signed16 ile düzeltildi
            r_volt = client.read_holding_registers(address=config['volt_addr'], count=1, slave=slave_id)
            val_volt = 0 if r_volt.isError() else to_signed16(r_volt.registers[0]) * config['volt_scale']
            time.sleep(0.05)

            # 3. Akım
            r_akim = client.read_holding_registers(address=config['akim_addr'], count=1, slave=slave_id)
            val_akim = 0 if r_akim.isError() else to_signed16(r_akim.registers[0]) * config['akim_scale']
            time.sleep(0.05)

            # 4. Sıcaklık — signed16 ile düzeltildi (örn: 0xFF9C = -100 → -10.0°C)
            r_isi = client.read_holding_registers(address=config['isi_addr'], count=1, slave=slave_id)
            val_isi = 0 if r_isi.isError() else to_signed16(r_isi.registers[0]) * config['isi_scale']
            time.sleep(0.05)

            

            # 5. Hata Kodları
            hata_kodu_189 = 0
            try:
                r_hata = client.read_holding_registers(address=189, count=2, slave=slave_id)
                if not r_hata.isError():
                    hata_kodu_189 = (r_hata.registers[0] << 16) | r_hata.registers[1]
            except Exception:
                pass

            hata_kodu_193 = 0
            try:
                time.sleep(0.05)
                r_hata2 = client.read_holding_registers(address=193, count=2, slave=slave_id)
                if not r_hata2.isError():
                    hata_kodu_193 = (r_hata2.registers[0] << 16) | r_hata2.registers[1]
            except Exception:
                pass

            return {
                "slave_id": slave_id,
                "guc": val_guc,
                "voltaj": val_volt,
                "akim": val_akim,
                "sicaklik": val_isi,
                "hata_kodu": hata_kodu_189,
                "hata_kodu_193": hata_kodu_193,
                "timestamp": datetime.now()
            }, None

        except ConnectionError as e:
            last_error = f"Bağlantı hatası: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(0.5)
                try:
                    client.close()
                    client.connect()
                except Exception:
                    pass
        except Exception as e:
            last_error = f"Okuma hatası: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(0.3)

    return None, last_error

def read_device(client, slave_id, config):
    return read_device_with_retry(client, slave_id, config, max_retries=3)


# --- STATE ---
if 'monitoring' not in st.session_state:
    st.session_state.monitoring = False
if 'ayarlar_kaydedildi' not in st.session_state:
    st.session_state.ayarlar_kaydedildi = False

# --- YAN MENÜ ---
with st.sidebar:
    st.header("🏭 PULSAR Ayarları")

    mevcut_ayarlar = veritabani.tum_ayarlari_oku()

    target_ip = st.text_input("IP Adresi", value=mevcut_ayarlar.get('target_ip', '10.35.14.10'))
    target_port = st.number_input("Port", value=int(mevcut_ayarlar.get('target_port', 502)), step=1)

    st.info("Virgül veya tire ile ayırın (Örn: 1, 2, 5-8)")
    id_input = st.text_input("İnverter ID Listesi", value=mevcut_ayarlar.get('slave_ids', '1,2,3'))
    target_ids, id_errors = utils.parse_id_list(id_input)

    if id_errors:
        st.warning(f"⚠️ Bazı ID'ler parse edilemedi: {', '.join(id_errors)}")

    st.write(f"📡 İzlenecek ID'ler: {utils.format_id_list_display(target_ids)}")

    st.divider()

    st.header("⏳ Zamanlayıcı")

    interval_options = {
        "1 dakika": 60,
        "10 dakika": 600,
        "30 dakika": 1800,
        "1 saat": 3600
    }

    current_refresh = float(mevcut_ayarlar.get('refresh_rate', 60))
    current_label = "1 dakika"
    for label, value in interval_options.items():
        if value == current_refresh:
            current_label = label
            break

    selected_interval = st.select_slider(
        "Veri Toplama Sıklığı",
        options=list(interval_options.keys()),
        value=current_label
    )

    refresh_rate = interval_options[selected_interval]
    st.info(f"⏱️ Seçilen: {selected_interval} ({refresh_rate} saniye)")

    st.markdown("---")
    st.header("🗺️ Adres Haritası")
    with st.expander("Detaylı Adres Ayarları"):
        c_guc_adr = st.number_input("Güç Adresi", value=int(mevcut_ayarlar.get('guc_addr', 70)))
        c_guc_sc = st.number_input("Güç Çarpan", value=float(mevcut_ayarlar.get('guc_scale', 1.0)), step=0.1, format="%.2f")

        c_volt_adr = st.number_input("Voltaj Adresi", value=int(mevcut_ayarlar.get('volt_addr', 71)))
        c_volt_sc = st.number_input("Voltaj Çarpan", value=float(mevcut_ayarlar.get('volt_scale', 1.0)), step=0.1, format="%.4f")

        c_akim_adr = st.number_input("Akım Adresi", value=int(mevcut_ayarlar.get('akim_addr', 72)))
        c_akim_sc = st.number_input("Akım Çarpan", value=float(mevcut_ayarlar.get('akim_scale', 0.1)), step=0.1, format="%.2f")

        c_isi_adr = st.number_input("Isı Adresi", value=int(mevcut_ayarlar.get('isi_addr', 74)))
        c_isi_sc = st.number_input("Isı Çarpan", value=float(mevcut_ayarlar.get('isi_scale', 1.0)), step=0.1, format="%.4f")

    config = {
        'guc_addr': c_guc_adr, 'guc_scale': c_guc_sc,
        'volt_addr': c_volt_adr, 'volt_scale': c_volt_sc,
        'akim_addr': c_akim_adr, 'akim_scale': c_akim_sc,
        'isi_addr': c_isi_adr, 'isi_scale': c_isi_sc,
    }

    # AYARLARI KAYDET BUTONU
    st.markdown("---")
    if st.button("💾 AYARLARI KALICI OLARAK KAYDET", type="primary"):
        veritabani.ayar_yaz('target_ip', target_ip)
        veritabani.ayar_yaz('target_port', target_port)
        veritabani.ayar_yaz('slave_ids', id_input)
        veritabani.ayar_yaz('refresh_rate', refresh_rate)
        veritabani.ayar_yaz('guc_addr', c_guc_adr)
        veritabani.ayar_yaz('guc_scale', c_guc_sc)
        veritabani.ayar_yaz('volt_addr', c_volt_adr)
        veritabani.ayar_yaz('volt_scale', c_volt_sc)
        veritabani.ayar_yaz('akim_addr', c_akim_adr)
        veritabani.ayar_yaz('akim_scale', c_akim_sc)
        veritabani.ayar_yaz('isi_addr', c_isi_adr)
        veritabani.ayar_yaz('isi_scale', c_isi_sc)

        st.success("✅ Ayarlar kaydedildi! Collector 30 saniye içinde güncellenecek.")
        kullanici = st.session_state.get('username', 'admin')
        veritabani.audit_log_kaydet(kullanici, "ayar_degistir", f"IP={target_ip}, Port={target_port}, IDs={id_input}")
        st.rerun()

    # Yenileme süresi ayarı
    st.markdown("---")
    st.header("⏱️ Yenileme Ayarları")

    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 30

    refresh_interval = st.select_slider(
        "Otomatik Yenileme Süresi",
        options=[5, 10, 15, 30, 60, 120],
        value=st.session_state.refresh_interval,
        format_func=lambda x: f"{x} saniye"
    )

    st.session_state.refresh_interval = refresh_interval

    st.caption(f"Panel {refresh_interval} saniyede bir yenilenecek")

    st.markdown("---")
    st.header("🎛️ Sistem Kontrolü")

    if st.button("▶️ SİSTEMİ BAŞLAT"):
        st.session_state.monitoring = True
        st.rerun()
    if st.button("⏹️ DURDUR"):
        st.session_state.monitoring = False
        st.rerun()

    st.markdown("---")
    st.header("🗑️ Veri Yönetimi")
    if st.button("Tüm Verileri Sil"):
        if veritabani.db_temizle():
            kullanici = st.session_state.get('username', 'admin')
            veritabani.audit_log_kaydet(kullanici, "veri_sil", "Tüm ölçüm verileri silindi")
            st.success("Temizlendi!")
            time.sleep(1)
            st.rerun()

# --- ANA EKRAN ---
st.title("⚡ Güneş Enerjisi Santrali İzleme")

section_header("📋", "Canlı Filo Durumu", "Tüm cihazların anlık durum özeti")

# --- Cihaz Sağlık Kartları ---
summary_for_cards = veritabani.tum_cihazlarin_son_durumu()
if summary_for_cards:
    num_devices = len(summary_for_cards)
    cols_per_row = min(num_devices, 4)
    gauge_cols = st.columns(cols_per_row)

    for idx, row in enumerate(summary_for_cards):
        col_idx = idx % cols_per_row
        dev_id = row[0]
        dev_guc = row[2] if row[2] is not None else 0
        dev_volt = row[3] if row[3] is not None else 0
        dev_akim = row[4] if row[4] is not None else 0
        dev_temp = row[5] if row[5] is not None else 0
        dev_hata = (row[6] if len(row) > 6 and row[6] else 0) or (row[7] if len(row) > 7 and row[7] else 0)

        if dev_hata:
            durum_emoji = "🔴"
            durum_renk = "#ef4444"
            durum_text = "ARIZA"
        elif dev_guc > 0:
            durum_emoji = "🟢"
            durum_renk = "#10b981"
            durum_text = "AKTİF"
        else:
            durum_emoji = "🟡"
            durum_renk = "#f59e0b"
            durum_text = "BEKLEMEDE"

        with gauge_cols[col_idx]:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=dev_guc,
                title={'text': f"{durum_emoji} ID:{dev_id}", 'font': {'size': 14, 'color': '#94a3b8', 'family': 'Inter'}},
                number={'suffix': 'W', 'font': {'size': 22, 'color': durum_renk, 'family': 'Inter'}},
                gauge={
                    'axis': {'range': [0, max(dev_guc * 1.5, 1000)], 'tickcolor': '#334155', 'tickfont': {'color': '#475569'}},
                    'bar': {'color': durum_renk},
                    'bgcolor': 'rgba(15, 23, 42, 0.6)',
                    'borderwidth': 1,
                    'bordercolor': 'rgba(255, 255, 255, 0.06)',
                    'steps': [
                        {'range': [0, max(dev_guc * 1.5, 1000) * 0.3], 'color': 'rgba(15, 23, 42, 0.4)'},
                        {'range': [max(dev_guc * 1.5, 1000) * 0.3, max(dev_guc * 1.5, 1000) * 0.7], 'color': 'rgba(30, 41, 59, 0.4)'},
                        {'range': [max(dev_guc * 1.5, 1000) * 0.7, max(dev_guc * 1.5, 1000)], 'color': 'rgba(99, 102, 241, 0.08)'},
                    ],
                },
            ))
            fig_gauge.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                height=185,
                margin=dict(l=20, r=20, t=40, b=10),
                font=dict(color='#94a3b8', family='Inter'),
            )
            st.plotly_chart(fig_gauge, width='stretch', key=f"gauge_{dev_id}")

            st.markdown(
                f'<div style="text-align:center; font-size:0.78rem; color:#94a3b8; margin-top:-10px; font-family: Inter, sans-serif;">'
                f'⚡{dev_volt}V &nbsp; 📈{dev_akim}A &nbsp; 🌡️{dev_temp}°C &nbsp; '
                f'<span style="color:{durum_renk};font-weight:700;">{durum_text}</span>'
                f'</div>', unsafe_allow_html=True
            )

table_spot = st.empty()

# --- Grafik Seçimi ---
st.markdown("---")

tab_tekli, tab_karsilastirma = st.tabs(["📊 Tekli Cihaz", "📈 Karşılaştırma"])

with tab_tekli:
    col_sel, col_info = st.columns([1, 3])
    with col_sel:
        selected_id = st.selectbox("Cihaz Seç:", target_ids, key="tek_cihaz")
    with col_info:
        st.info("⚠️ Detaylı arıza kodlarını görmek için sol menüden **Alarmlar** sayfasına gidin.")

with tab_karsilastirma:
    karsilastirma_ids = st.multiselect("Karşılaştırılacak Cihazlar:", target_ids, default=target_ids[:3])
    karsilastirma_metrik = st.selectbox("Metrik:", ["guc", "voltaj", "akim", "sicaklik"],
                                         format_func=lambda x: {"guc": "☀️ Güç (W)", "voltaj": "⚡ Voltaj (V)",
                                                                  "akim": "📈 Akım (A)", "sicaklik": "🌡️ Sıcaklık (°C)"}[x])


# --- Plotly Grafik Yardımcıları ---
def create_plotly_chart(df, column, title, color, unit=""):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df[column],
        mode='lines',
        line=dict(color=color, width=2.5),
        fill='tozeroy',
        fillcolor=color.replace(')', ',0.08)').replace('rgb', 'rgba'),
        hovertemplate=f'%{{x|%H:%M:%S}}<br>{title}: %{{y:.1f}} {unit}<extra></extra>',
        name=title
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10, 14, 26, 0.5)',
        margin=dict(l=10, r=10, t=35, b=10),
        height=260,
        title=dict(text=title, font=dict(size=13, color='#94a3b8', family='Inter')),
        xaxis=dict(gridcolor='rgba(255,255,255,0.04)', showgrid=True, zeroline=False),
        yaxis=dict(gridcolor='rgba(255,255,255,0.04)', showgrid=True, zeroline=False),
        font=dict(color='#94a3b8', family='Inter'),
        hovermode='x unified',
    )
    return fig


def create_comparison_chart(ids, metric, title, colors):
    fig = go.Figure()
    for i, dev_id in enumerate(ids):
        data = veritabani.son_verileri_getir(dev_id, limit=100)
        if not data:
            continue
        try:
            df = pd.DataFrame(data, columns=["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_193"])
        except Exception:
            df = pd.DataFrame(data, columns=["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu"])
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        color = colors[i % len(colors)]
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df[metric],
            mode='lines', name=f'ID {dev_id}',
            line=dict(color=color, width=2.5),
        ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10, 14, 26, 0.5)',
        margin=dict(l=10, r=10, t=40, b=10),
        height=360,
        title=dict(text=title, font=dict(size=14, color='#94a3b8', family='Inter')),
        xaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
        font=dict(color='#94a3b8', family='Inter'),
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8')
        ),
    )
    return fig


# --- Grafik Yer Tutucuları (Tekli) ---
row1_c1, row1_c2 = st.columns(2)
row2_c1, row2_c2 = st.columns(2)
with row1_c1:
    chart_guc = st.empty()
with row1_c2:
    chart_volt = st.empty()
with row2_c1:
    chart_akim = st.empty()
with row2_c2:
    chart_isi = st.empty()

# Karşılaştırma Grafiği Yer Tutucusu
chart_karsilastirma = st.empty()

# --- DURUM ÇUBUĞU ---
status_spot = st.empty()


def ui_refresh():
    # 1. TABLO GÜNCELLEME
    summary_data = veritabani.tum_cihazlarin_son_durumu()
    if summary_data:
        df_sum = pd.DataFrame([row[:6] for row in summary_data], columns=["ID", "Son Zaman", "Güç (W)", "Voltaj (V)", "Akım (A)", "Isı (C)"])
        df_sum["Son Zaman"] = pd.to_datetime(df_sum["Son Zaman"]).dt.strftime('%H:%M:%S')
        table_spot.dataframe(df_sum.set_index("ID"), width='stretch')

    # 2. PLOTLY GRAFİK GÜNCELLEME (Tekli)
    detail_data = veritabani.son_verileri_getir(selected_id, limit=100)
    if detail_data:
        try:
            df_det = pd.DataFrame(detail_data, columns=["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_193"])
        except Exception:
            df_det = pd.DataFrame(detail_data, columns=["timestamp", "guc", "voltaj", "akim", "sicaklik", "hata_kodu"])

        df_det["timestamp"] = pd.to_datetime(df_det["timestamp"])
        df_det = df_det.set_index("timestamp")

        chart_guc.plotly_chart(create_plotly_chart(df_det, "guc", "☀️ Güç", "rgb(255,215,0)", "W"), width='stretch', key="p_guc")
        chart_volt.plotly_chart(create_plotly_chart(df_det, "voltaj", "⚡ Voltaj", "rgb(99,102,241)", "V"), width='stretch', key="p_volt")
        chart_akim.plotly_chart(create_plotly_chart(df_det, "akim", "📈 Akım", "rgb(16,185,129)", "A"), width='stretch', key="p_akim")
        chart_isi.plotly_chart(create_plotly_chart(df_det, "sicaklik", "🌡️ Sıcaklık", "rgb(239,83,80)", "°C"), width='stretch', key="p_isi")

    # 3. KARŞILAŞTIRMA GRAFİĞİ
    if karsilastirma_ids:
        colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#a855f7', '#f97316', '#22d3ee', '#e879f9']
        metrik_labels = {"guc": "☀️ Güç Karşılaştırma (W)", "voltaj": "⚡ Voltaj Karşılaştırma (V)",
                         "akim": "📈 Akım Karşılaştırma (A)", "sicaklik": "🌡️ Sıcaklık Karşılaştırma (°C)"}
        chart_karsilastirma.plotly_chart(
            create_comparison_chart(karsilastirma_ids, karsilastirma_metrik, metrik_labels[karsilastirma_metrik], colors),
            width='stretch', key="p_comp"
        )


# --- ANA DÖNGÜ ---
if st.session_state.monitoring:
    client = get_modbus_client(target_ip, target_port)
    with status_spot:
        status_bar(True, f'✅ <b>Canlı İzleme Aktif</b> — Otomatik yenileme: {st.session_state.refresh_interval} saniye')

    # Veri toplama
    for dev_id in target_ids:
        data, err = read_device(client, dev_id, config)
        if data:
            veritabani.veri_ekle(dev_id, data)
        elif err:
            st.warning(f"⚠️ ID {dev_id} okunamadı: {err}")

    ui_refresh()

    time.sleep(st.session_state.refresh_interval)
    st.rerun()
else:
    ui_refresh()
    with status_spot:
        status_bar(False, '💤 <b>Sistem Beklemede</b> — Grafikleri görmek için BAŞLAT\'a basın.')