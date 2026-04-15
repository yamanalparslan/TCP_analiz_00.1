import streamlit as st
import pandas as pd
from datetime import datetime
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
import utils
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Günlük Raporlar", page_icon="📊", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()
veritabani.init_db()

st.title("📊 Günlük Performans ve Üretim Raporu")
section_header("📈", "Üretim Analizi", "Seçilen tarihe göre tüm cihazların üretim ve verimlilik özeti")

ayarlar = veritabani.tum_ayarlari_oku()
slave_ids_raw = ayarlar.get('slave_ids', '1,2,3')
slave_ids, parse_errors = utils.parse_id_list(slave_ids_raw)
if parse_errors:
    st.warning("⚠️ Parse hatası: " + ", ".join(parse_errors))

col_date, _ = st.columns([1, 2])
with col_date:
    secilen_tarih = st.date_input("Rapor Tarihi:", datetime.now())
tarih_str = secilen_tarih.strftime('%Y-%m-%d')

rapor_listesi = []
for s_id in slave_ids:
    uretim = veritabani.gunluk_uretim_hesapla(tarih_str, slave_id=s_id)
    istatistik = veritabani.tarih_araliginda_ortalamalar(tarih_str, tarih_str, slave_id=s_id)
    hatalar = veritabani.hata_sayilarini_getir(tarih_str, tarih_str, slave_id=s_id)
    if istatistik and istatistik.get('toplam_olcum', 0) > 0:
        hata_str = "0/0"
        if hatalar:
            hata_str = str(hatalar['hata_189_sayisi']) + " / " + str(hatalar['hata_193_sayisi'])
        rapor_listesi.append({
            "Cihaz ID": s_id,
            "Üretim (kWh)": uretim['uretim_kwh'] if uretim else 0,
            "Ort. Güç (W)": round(istatistik['ort_guc'], 2),
            "Maks. Güç (W)": istatistik['max_guc'],
            "Ort. Voltaj (V)": round(istatistik['ort_voltaj'], 1),
            "Ort. Sıcaklık (°C)": round(istatistik['ort_sicaklik'], 1),
            "Hata (189/193)": hata_str,
            "Çalışma (Saat)": uretim['calisma_suresi_saat'] if uretim else 0
        })
if rapor_listesi:
    df_rapor = pd.DataFrame(rapor_listesi)
    total_kwh = df_rapor["Üretim (kWh)"].sum()
    total_errors = sum([int(x.split('/')[0].strip()) + int(x.split('/')[1].strip()) for x in df_rapor["Hata (189/193)"]])
    kpi_row([
        {"value": str(round(total_kwh, 2)) + " kWh", "label": "Toplam Üretim", "color": "#f59e0b"},
        {"value": str(len(df_rapor)), "label": "Aktif Cihaz", "color": "#10b981"},
        {"value": str(total_errors), "label": "Toplam Hata", "color": "#ef4444"},
    ])
    st.markdown("<br>", unsafe_allow_html=True)
    st.dataframe(df_rapor.set_index("Cihaz ID"), width='stretch')
    csv = df_rapor.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 CSV İndir", csv, "gunluk_rapor_" + tarih_str + ".csv", "text/csv")
else:
    st.markdown('<div class="glossy-card" style="text-align:center;"><div style="font-size:2rem; margin-bottom:8px;">📭</div><div style="font-size:1rem; color:#94a3b8; font-family:Inter,sans-serif;">Seçilen tarihte veri bulunamadı.</div></div>', unsafe_allow_html=True)
