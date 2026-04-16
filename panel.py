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
    page_icon="",
    initial_sidebar_state="expanded"
)

# --- AUTH KONTROLU ---
if not check_auth():
    st.stop()

# DB Baslat
veritabani.init_db()

# --- GLOSSY CSS TEMA ---
inject_glossy_css()
logout_button()

# --- YARDIMCI FONKSIYONLAR ---

@st.cache_resource
def get_modbus_client(ip, port):
    return ModbusTcpClient(ip, port=port, timeout=2)

def to_signed16(value: int) -> int:
    """Modbus unsigned 16-bit register' signed int'e cevirir."""
    return value - 65536 if value > 32767 else value

def read_device_with_retry(client, slave_id, config, max_retries=3):
    last_error = None

    for attempt in range(max_retries):
        try:
            if not client.connected:
                client.connect()
                if not client.connected:
                    last_error = "Baglanti kurulamadi"
                    if attempt < max_retries - 1:
                        time.sleep(0.5)
                        continue
                    return None, last_error

            # 1. Guc
            r_guc = client.read_holding_registers(address=config['guc_addr'], count=1, slave=slave_id)
            if r_guc.isError():
                last_error = f"Guc okunamadi (ID:{slave_id})"
                if attempt < max_retries - 1:
                    time.sleep(0.3)
                    try:
                        client.close()
                    except Exception:
                        pass
                    continue
                return None, last_error
            val_guc = r_guc.registers[0] * config['guc_scale']  # Guc negatif olmaz, signed gerekmez
            time.sleep(0.05)  #  Okumalar aras kucuk bekleme

            # 2. Voltaj  signed16 ile duzeltildi
            r_volt = client.read_holding_registers(address=config['volt_addr'], count=1, slave=slave_id)
            val_volt = 0 if r_volt.isError() else utils.to_signed16(r_volt.registers[0]) * config['volt_scale']
            time.sleep(0.05)

            # 3. Akm
            r_akim = client.read_holding_registers(address=config['akim_addr'], count=1, slave=slave_id)
            val_akim = 0 if r_akim.isError() else utils.to_signed16(r_akim.registers[0]) * config['akim_scale']
            time.sleep(0.05)

            # 4. Scaklk  signed16 ile duzeltildi (orn: 0xFF9C = -100  -10.0C)
            r_isi = client.read_holding_registers(address=config['isi_addr'], count=1, slave=slave_id)
            val_isi = 0 if r_isi.isError() else utils.decode_temperature_register(r_isi.registers[0], config['isi_scale'])
            
            if r_isi.isError():
                val_isi = 0
            else:
                raw_isi = r_isi.registers[0]
                val_isi = raw_isi * config['isi_scale']  # signed kaldrld
            time.sleep(0.05)

            

            # 5. Hata Kodlar
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

            if not r_isi.isError():
                val_isi = utils.decode_temperature_register(r_isi.registers[0], config['isi_scale'])

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
            last_error = f"Baglanti hatasi: {str(e)}"
            if attempt < max_retries - 1:
                time.sleep(0.5)
                try:
                    client.close()
                    client.connect()
                except Exception:
                    pass
        except Exception as e:
            last_error = f"Okuma hatasi: {str(e)}"
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

# --- YAN MENU ---
with st.sidebar:
    st.header("PULSAR Ayarlari")

    mevcut_ayarlar = veritabani.tum_ayarlari_oku()

    target_ip = st.text_input("IP Adresi", value=mevcut_ayarlar.get('target_ip', '10.35.14.10'))
    target_port = st.number_input("Port", value=int(mevcut_ayarlar.get('target_port', 502)), step=1)

    st.info("Virgul veya tire ile ayirin (Orn: 1, 2, 5-8)")
    id_input = st.text_input("Inverter ID Listesi", value=mevcut_ayarlar.get('slave_ids', '1,2,3'))
    target_ids, id_errors = utils.parse_id_list(id_input)

    if id_errors:
        st.warning(f"Bazi ID'ler parse edilemedi: {', '.join(id_errors)}")

    st.write(f"Izlenecek ID'ler: {utils.format_id_list_display(target_ids)}")

    st.divider()

    st.header("Zamanlayici")

    interval_options = {
        "1 dakika": 60,
        "10 dakika": 600,
        "30 dakika": 1800,
        "1 saat": 3600,
        "2 saat": 7200
    }

    current_refresh = float(mevcut_ayarlar.get('refresh_rate', 600))
    current_label = "10 dakika"
    for label, value in interval_options.items():
        if value == current_refresh:
            current_label = label
            break

    selected_interval = st.select_slider(
        "Veri Toplama Sikligi",
        options=list(interval_options.keys()),
        value=current_label
    )

    refresh_rate = interval_options[selected_interval]
    st.info(f" Secilen: {selected_interval} ({refresh_rate} saniye)")

    st.markdown("---")
    st.header("Adres Haritasi")
    with st.expander("Detayli Adres Ayarlari"):
        c_guc_adr = st.number_input("Guc Adresi", value=int(mevcut_ayarlar.get('guc_addr', 70)))
        c_guc_sc = st.number_input("Guc Carpan", value=float(mevcut_ayarlar.get('guc_scale', 1.0)), step=0.1, format="%.2f")

        c_volt_adr = st.number_input("Voltaj Adresi", value=int(mevcut_ayarlar.get('volt_addr', 71)))
        c_volt_sc = st.number_input("Voltaj Carpan", value=float(mevcut_ayarlar.get('volt_scale', 1.0)), step=0.1, format="%.4f")

        c_akim_adr = st.number_input("Akim Adresi", value=int(mevcut_ayarlar.get('akim_addr', 72)))
        c_akim_sc = st.number_input("Akim Carpani", value=float(mevcut_ayarlar.get('akim_scale', 0.1)), step=0.1, format="%.2f")

        c_isi_adr = st.number_input("Isi Adresi", value=int(mevcut_ayarlar.get('isi_addr', 74)))
        c_isi_sc = st.number_input("Isi Carpani", value=float(mevcut_ayarlar.get('isi_scale', 0.001)), step=0.1, format="%.4f")

    config = {
        'guc_addr': c_guc_adr, 'guc_scale': c_guc_sc,
        'volt_addr': c_volt_adr, 'volt_scale': c_volt_sc,
        'akim_addr': c_akim_adr, 'akim_scale': c_akim_sc,
        'isi_addr': c_isi_adr, 'isi_scale': c_isi_sc,
    }

    # AYARLARI KAYDET BUTONU
    st.markdown("---")
    if st.button("AYARLARI KALICI OLARAK KAYDET", type="primary"):
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

        st.success("Ayarlar kaydedildi! Collector 30 saniye icinde guncellenecek.")
        kullanici = st.session_state.get('username', 'admin')
        veritabani.audit_log_kaydet(kullanici, "ayar_degistir", f"IP={target_ip}, Port={target_port}, IDs={id_input}")
        st.rerun()

    # Yenileme suresi ayar
    st.markdown("---")
    st.header("Yenileme Ayarlari")

    if 'refresh_interval' not in st.session_state:
        st.session_state.refresh_interval = 30

    refresh_interval = st.select_slider(
        "Otomatik Yenileme Suresi",
        options=[10, 15, 30, 60, 120, 300, 600, 1800, 3600, 7200],
        value=st.session_state.refresh_interval,
        format_func=lambda x: f"{x} saniye"
    )

    st.session_state.refresh_interval = refresh_interval

    st.caption(f"Panel {refresh_interval} saniyede bir yenilenecek")

    st.markdown("---")
    st.header(" Sistem Kontrolu")

    if st.button("SISTEMI BASLAT"):
        st.session_state.monitoring = True
        st.rerun()
    if st.button(" DURDUR"):
        st.session_state.monitoring = False
        st.rerun()

    st.markdown("---")
    st.header(" Veri Yonetimi")
    if st.button("Tum Verileri Sil"):
        if veritabani.db_temizle():
            kullanici = st.session_state.get('username', 'admin')
            veritabani.audit_log_kaydet(kullanici, "veri_sil", "Tum olcum verileri silindi")
            st.success("Temizlendi!")
            time.sleep(1)
            st.rerun()

# --- ANA EKRAN ---
st.title("Gunes Enerjisi Santrali Izleme")

section_header("", "Canli Filo Durumu", "Tum cihazlarin anlik durum ozeti")

# --- Cihaz Saglk Kartlar ---
summary_for_cards = veritabani.tum_cihazlarin_son_durumu()
if summary_for_cards:
    num_devices = len(summary_for_cards)
    cols_per_row = min(num_devices, 4)
    gauge_cols = st.columns(cols_per_row)

    for idx, row in enumerate(summary_for_cards):
        col_idx = idx % cols_per_row
        dev_id = row[0]
        dev_guc = row[2] if row[2] is not None else 0
        dev_volt = round(float(row[3]), 1) if row[3] is not None else 0
        dev_akim = round(float(row[4]), 2) if row[4] is not None else 0
        dev_temp = round(utils.normalize_temperature_value(row[5]), 1) if row[5] is not None else 0
        dev_hata = (row[6] if len(row) > 6 and row[6] else 0) or (row[7] if len(row) > 7 and row[7] else 0)

        if dev_hata:
            durum_emoji = ""
            durum_renk = "#ef4444"
            durum_text = "ARIZA"
        elif dev_guc > 0:
            durum_emoji = ""
            durum_renk = "#10b981"
            durum_text = "AKTIF"
        else:
            durum_emoji = ""
            durum_renk = "#f59e0b"
            durum_text = "BEKLEMEDE"

        with gauge_cols[col_idx]:
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=dev_guc,
                title={'text': f"{durum_emoji} ID:{dev_id}", 'font': {'size': 14, 'color': '#94a3b8', 'family': 'Inter'}},
                number={'suffix': 'W', 'font': {'size': 22, 'color': durum_renk, 'family': 'Inter'}},
                gauge={
                    'axis': {'range': [0, 5000], 'tickcolor': '#334155', 'tickfont': {'color': '#475569'}},
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
                f'{dev_volt:.1f}V &nbsp; {dev_akim:.2f}A &nbsp; {dev_temp:.1f}C'
                f'<span style="color:{durum_renk};font-weight:700;">{durum_text}</span>'
                f'</div>', unsafe_allow_html=True
            )

table_spot = st.empty()

# --- Grafik Secimi ---
st.markdown("---")

tab_tekli, tab_karsilastirma = st.tabs([" Tekli Cihaz", "Karsilastirma"])

with tab_tekli:
    col_sel, col_info = st.columns([1, 3])
    with col_sel:
        selected_id = st.selectbox("Cihaz Sec:", target_ids, key="tek_cihaz")
    with col_info:
        st.info(" Detayli ariza kodlarini gormek icin sol menuden **Alarmlar** sayfasina gidin.")

with tab_karsilastirma:
    karsilastirma_ids = st.multiselect("Karsilastirilacak Cihazlar:", target_ids, default=target_ids[:3])
    karsilastirma_metrik = st.selectbox("Metrik:", ["guc", "voltaj", "akim", "sicaklik"],
                                         format_func=lambda x: {"guc": " Guc (W)", "voltaj": " Voltaj (V)",
                                                                  "akim": "Akim (A)", "sicaklik": "Sicaklik (C)"}[x])


# --- Plotly Grafik Yardmclar ---
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
            
        # DUZELTME 1: Veritabanndan gelen veriyi guvenli parse etme
        df = pd.DataFrame(data)
        
        # Tuple icindeki verilerin (id, slave_id, timestamp, guc, voltaj, akim, sicaklik...) 
        # dogru eslestiginden emin olmak icin esnek yap (sutun saysna gore tahmin)
        if len(df.columns) >= 7:
            # Sutunlar isimleriyle degil, son sutunlar alacak sekilde ayarlayalm
            # Varsaym: timestamp, guc, voltaj, akim, sicaklik sondan bir oncekilerdir.
            # En guvenlisi veritaban yapnza gore bu indexleri degistirmektir.
            df = df.rename(columns={
                df.columns[1]: "timestamp", # Genelde 2. veya 3. sutun timestamp olur
                df.columns[2]: "guc",
                df.columns[3]: "voltaj",
                df.columns[4]: "akim",
                df.columns[5]: "sicaklik"
            })
        
        # DUZELTME 2: Zaman datetime yap ve KRONOLOJIK srala!
        if "sicaklik" in df.columns:
            df["sicaklik"] = pd.to_numeric(df["sicaklik"], errors='coerce').apply(utils.normalize_temperature_value)
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
        df = df.dropna(subset=['timestamp']) # Hatal tarihleri ucur
        df = df.sort_values(by="timestamp", ascending=True) # ZAMANA GORE SIRALA

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


# --- Grafik Yer Tutucular (Tekli) ---
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

# Karslastrma Grafigi Yer Tutucusu
chart_karsilastirma = st.empty()

# --- DURUM CUBUU ---
status_spot = st.empty()


def ui_refresh():
    # 1. TABLO GUNCELLEME
    summary_data = veritabani.tum_cihazlarin_son_durumu()
    if summary_data:
        df_sum = pd.DataFrame([row[:6] for row in summary_data], columns=["ID", "Son Zaman", "Guc (W)", "Voltaj (V)", "Akim (A)", "Isi (C)"])
        df_sum["Son Zaman"] = pd.to_datetime(df_sum["Son Zaman"], errors='ignore').astype(str).str.extract(r'(\d{2}:\d{2}:\d{2})')[0]
        df_sum[df_sum.columns[-1]] = pd.to_numeric(df_sum[df_sum.columns[-1]], errors='coerce').fillna(0).apply(utils.normalize_temperature_value).round(1)
        table_spot.dataframe(df_sum.set_index("ID"), width='stretch')

    # 2. PLOTLY GRAFIK GUNCELLEME (Tekli)
    detail_data = veritabani.son_verileri_getir(selected_id, limit=100)
    if detail_data:
        # Tuple Index Mapping - Eger veritaban SELECT * donuyorsa:
        # 0: id, 1: slave_id, 2: timestamp, 3: guc, 4: voltaj, 5: akim, 6: sicaklik, 7: hata_kodu
        # AAIDAKI INDEKSLERI VERITABANINIZA GORE KONTROL EDIN
        try:
            df_det = pd.DataFrame(detail_data)
            df_det = df_det.rename(columns={
                df_det.columns[-7]: "timestamp", # Sondan 7. sutun
                df_det.columns[-6]: "guc",
                df_det.columns[-5]: "voltaj",
                df_det.columns[-4]: "akim",
                df_det.columns[-3]: "sicaklik"
            })
            
            # Tarih format ve sralama (Grafiklerin duzgun cizilmesi icin sart)
            df_det["sicaklik"] = pd.to_numeric(df_det["sicaklik"], errors='coerce').apply(utils.normalize_temperature_value)
            df_det["timestamp"] = pd.to_datetime(df_det["timestamp"], errors='coerce')
            df_det = df_det.dropna(subset=['timestamp']).sort_values("timestamp", ascending=True)
            df_det = df_det.set_index("timestamp")

            # DUZELTME 3: st.empty() icine basarken key argumanlarn KALDIRDIK.
            # Streamlit statik keyler yuzunden grafik guncellememezlik yapmayacak.
            chart_guc.plotly_chart(create_plotly_chart(df_det, "guc", " Guc", "rgb(255,215,0)", "W"), use_container_width=True)
            chart_volt.plotly_chart(create_plotly_chart(df_det, "voltaj", " Voltaj", "rgb(99,102,241)", "V"), use_container_width=True)
            chart_akim.plotly_chart(create_plotly_chart(df_det, "akim", "Akim", "rgb(16,185,129)", "A"), use_container_width=True)
            chart_isi.plotly_chart(create_plotly_chart(df_det, "sicaklik", "Sicaklik", "rgb(239,83,80)", "C"), use_container_width=True)
        except Exception as e:
            st.error(f"Grafik verisi islenirken hata: {e}")

    # 3. KARILATIRMA GRAFII
    if karsilastirma_ids:
        colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#a855f7', '#f97316', '#22d3ee', '#e879f9']
        metrik_labels = {"guc": " Guc Karslastrma (W)", "voltaj": " Voltaj Karslastrma (V)",
                         "akim": " Akm Karslastrma (A)", "sicaklik": " Scaklk Karslastrma (C)"}
        
        # Key'i dinamik yaptk (opsiyonel)
        chart_karsilastirma.plotly_chart(
            create_comparison_chart(karsilastirma_ids, karsilastirma_metrik, metrik_labels[karsilastirma_metrik], colors),
            use_container_width=True
        )


# --- ANA DONGU ---
if st.session_state.monitoring:
    client = get_modbus_client(target_ip, target_port)
    with status_spot:
        status_bar(True, f' <b>Canli Izleme Aktif</b>  Otomatik yenileme: {st.session_state.refresh_interval} saniye')

    # Veri toplama
    for dev_id in target_ids:
        data, err = read_device(client, dev_id, config)
        if data:
            veritabani.veri_ekle(dev_id, data)
        elif err:
            st.warning(f" ID {dev_id} okunamad: {err}")

    ui_refresh()

    time.sleep(st.session_state.refresh_interval)
    st.rerun()
else:
    ui_refresh()
    with status_spot:
        status_bar(False, ' <b>Sistem Beklemede</b>  Grafikleri gormek icin BALAT\'a basn.')

