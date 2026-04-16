import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor
import sys, os
import math

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
import utils
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Uretim Tahmini", page_icon="", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()
veritabani.init_db()

st.title("AI Destekli Uretim Tahmini")
section_header("", "Makine Ogrenmesi Modeli", "Gecmis verilere dayanarak gelecek uretim kapasitesini ongorun")

# Cihazlari getir
ayarlar = veritabani.tum_ayarlari_oku()
slave_ids, _ = utils.parse_id_list(ayarlar.get('slave_ids', '1,2,3'))

# Ayarlar Alani
col_settings, col_info = st.columns([1, 2])
with col_settings:
    hedef_cihaz = st.selectbox("Hedef Cihaz Secin:", ["Tum Cihazlar (Ort)"] + [f"ID {s}" for s in slave_ids])
    tahmin_periyodu = st.radio("Tahmin Suresi:", ["Gelecek 24 Saat", "Gelecek 7 Gun"], horizontal=True)
    hava_durumu = st.select_slider("Beklenen Hava Durumu:", options=["Bulutlu (Dusuk)", "Parcali Bulutlu", "Gunesli (Yuksek)"], value="Parcali Bulutlu")

with col_info:
    st.markdown("""
        <div class="glossy-card" style="padding:15px; margin-top:28px;">
            <div style="font-weight:600; color:#38bdf8; margin-bottom:5px;">Model Bilgisi</div>
            <div style="font-size:0.9rem; color:#94a3b8;">
            <b>Algoritma:</b> Random Forest Regressor<br>
            Bu model son 10.000 veri olcumunu temel alarak gunun saati ve ortam sicakligi ile guc uretimi arasindaki iliskiyi ogrenir. Gelecek projeksiyonu secilen hava durumuna gore simule edilmistir. Eksi degerli veriler filtrelenmistir.
            </div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

if st.button("Tahmini Baslat", type="primary"):
    with st.spinner("Gecmis veriler analiz ediliyor ve model egitiliyor..."):
        
        # 1. Veri Hazirligi
        veriler = []
        if hedef_cihaz == "Tum Cihazlar (Ort)":
            hedef_idler = slave_ids
        else:
            hedef_idler = [int(hedef_cihaz.split(' ')[-1])]
            
        for sid in hedef_idler:
            satirlar = veritabani.son_verileri_getir(sid, limit=5000)
            if satirlar:
                for row in satirlar:
                    # ts, guc, voltaj, akim, sicaklik, hk1, hk2
                    veriler.append({
                        "ts": pd.to_datetime(row[0]),
                        "guc": float(row[1]),
                        "sicaklik": float(row[4])
                    })
                    
        if len(veriler) < 100:
            st.error("Modeli egitmek icin yetersiz veri! En az 100 kayit gereklidir.")
        else:
            df = pd.DataFrame(veriler)
            df = df[df['guc'] > 0] # Sifir ve negatifleri dahil etmeyelim
            if len(df) < 50:
                 st.error("Gun icinde yeterince olcum (Guc > 0) bulunamadi.")
            else:
                df['saat'] = df['ts'].dt.hour
                df['dakika'] = df['ts'].dt.minute
                
                # Sadece saat ve sicaklik bagimsiz degisken, guc bagimli degisken
                X = df[['saat', 'sicaklik']]
                y = df['guc']
                
                model = RandomForestRegressor(n_estimators=50, random_state=42, max_depth=10)
                model.fit(X, y)
                
                # 2. Gelecek Verisi Turetme
                now = datetime.now()
                gelecek_verisi = []
                saatlik_nokta = 60 # 24 saat = 24 nokta, ama biz saat basi 1 veri mi koyalimInfinite evet.
                
                delta_saat = 24 if "24 Saat" in tahmin_periyodu else (24 * 7)
                
                base_temp = 25
                if hava_durumu == "Bulutlu (Dusuk)":
                    base_temp = 18
                    guc_carpani = 0.6
                elif hava_durumu == "Gunesli (Yuksek)":
                    base_temp = 32
                    guc_carpani = 1.2
                else:
                    guc_carpani = 0.9
                    
                for i in range(1, delta_saat + 1):
                    gelecekteki_zaman = now + timedelta(hours=i)
                    gelecek_saat = gelecekteki_zaman.hour
                    
                    # Sicaklik simlasyonu (len sicak, gece soguk)
                    isinma_katsayisi = -math.cos(math.pi * gelecek_saat / 12) if 'math' in locals() else np.cos((gelecek_saat - 14)*np.pi/12)
                    sim_sicaklik = base_temp + (isinma_katsayisi * 7) # gece base_temp-7, gndz base_temp+7
                    
                    gelecek_verisi.append({
                        "ts": gelecekteki_zaman,
                        "saat": gelecek_saat,
                        "sicaklik": sim_sicaklik
                    })
                    
                df_gelecek = pd.DataFrame(gelecek_verisi)
                
                # Tahminleme
                tahmin_X = df_gelecek[['saat', 'sicaklik']]
                raw_pred = model.predict(tahmin_X)
                
                # Gece (19:00 - 05:00 arasi vs gucunu 0 yap (basit mask))
                gece_mask = (df_gelecek['saat'] < 5) | (df_gelecek['saat'] > 19)
                raw_pred = np.where(gece_mask, 0, raw_pred)
                
                # Carpani ugula
                df_gelecek['tahmini_guc'] = raw_pred * guc_carpani
                df_gelecek['tahmini_guc'] = df_gelecek['tahmini_guc'].clip(lower=0) 
                
                toplam_kwh = (df_gelecek['tahmini_guc'].sum() / 1000.0)
                
                if hedef_cihaz == "Tum Cihazlar (Ort)":
                    toplam_kwh = toplam_kwh * len(slave_ids) # Ortalama x Cihaz sayisi tahmin
                
                # KPI Kartlari
                kpi_row([
                    {"value": f"{toplam_kwh:.2f} kWh", "label": f"Beklenen Toplam Uretim ({tahmin_periyodu})", "color": "#10b981"},
                    {"value": f"{df_gelecek['tahmini_guc'].max():.0f} W", "label": "Beklenen Tepe Guc", "color": "#f59e0b"},
                    {"value": f"{df_gelecek['sicaklik'].max():.1f} C", "label": "Maks. Beklenen Ortam Isisi", "color": "#ef4444"},
                ])
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Grafik
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_gelecek['ts'],
                    y=df_gelecek['tahmini_guc'],
                    mode='lines+markers',
                    name='Tahmini Guc (W)',
                    line=dict(color='#0ea5e9', width=3, shape='spline'),
                    fill='tozeroy',
                    fillcolor='rgba(14, 165, 233, 0.2)',
                    marker=dict(size=6, color='#38bdf8')
                ))
                
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(10,14,26,0.5)',
                    height=450,
                    margin=dict(l=10, r=10, t=20, b=10),
                    xaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
                    yaxis=dict(gridcolor='rgba(255,255,255,0.04)', title="Guc (W)"),
                    font=dict(color='#94a3b8', family='Inter'),
                    hovermode='x unified',
                    legend=dict(bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8'))
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.success("Tahmin tamamlandi. Model, gecmis verileri kullanarak secilen hava durumuna gore sentetik bir uretim tahmini olusturdu.")
