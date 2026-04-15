import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani, utils
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Karşılaştırma", page_icon="⚖️", layout="wide")

if not check_auth():
    st.stop()

inject_glossy_css()
logout_button()

veritabani.init_db()

st.title("⚖️ Cihaz Karşılaştırma")
section_header("📊", "Çoklu Cihaz Analizi", "Seçilen cihazların performansını yan yana karşılaştırın")

ayarlar = veritabani.tum_ayarlari_oku()
slave_ids, _ = utils.parse_id_list(ayarlar.get('slave_ids', '1,2,3'))

secili = st.multiselect("Karşılaştırılacak Cihazlar:", slave_ids, default=slave_ids[:3])
metrik = st.selectbox("Metrik:", ["guc", "voltaj", "akim", "sicaklik"],
    format_func=lambda x: {"guc": "☀️ Güç (W)", "voltaj": "⚡ Voltaj (V)", "akim": "📈 Akım (A)", "sicaklik": "🌡️ Sıcaklık (°C)"}[x])

metrik_birim = {"guc": "W", "voltaj": "V", "akim": "A", "sicaklik": "°C"}
metrik_baslik = {"guc": "☀️ Güç Karşılaştırma", "voltaj": "⚡ Voltaj Karşılaştırma", "akim": "📈 Akım Karşılaştırma", "sicaklik": "🌡️ Sıcaklık Karşılaştırma"}

# Veritabanından dönen sütunlar: zaman, guc, voltaj, akim, sicaklik, hata_kodu, hata_kodu_193
DB_COLUMNS = ["ts", "guc", "voltaj", "akim", "sicaklik", "hata_kodu", "hata_kodu_193"]

if secili:
    colors = ['#6366f1', '#ec4899', '#10b981', '#f59e0b', '#a855f7', '#f97316', '#22d3ee', '#e879f9']
    fig = go.Figure()
    ozet_veriler = []

    for i, did in enumerate(secili):
        data = veritabani.son_verileri_getir(did, limit=200)
        if not data:
            continue
        
        # Sütun sayısına göre uyumlu DataFrame oluştur
        num_cols = len(data[0]) if data else 0
        cols = DB_COLUMNS[:num_cols]
        df = pd.DataFrame(data, columns=cols)
        df["ts"] = pd.to_datetime(df["ts"])
        
        if metrik not in df.columns:
            continue
        
        fig.add_trace(go.Scatter(
            x=df["ts"], y=df[metrik],
            mode='lines',
            name=f'ID {did}',
            line=dict(color=colors[i % len(colors)], width=2.5)
        ))

        # Özet istatistik topla
        ozet_veriler.append({
            "Cihaz": f"ID {did}",
            "Ortalama": round(df[metrik].mean(), 2),
            "Maks": round(df[metrik].max(), 2),
            "Min": round(df[metrik].min(), 2),
        })

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(10,14,26,0.5)',
        height=450,
        margin=dict(l=10, r=10, t=40, b=10),
        title=dict(text=metrik_baslik[metrik], font=dict(size=14, color='#94a3b8', family='Inter')),
        xaxis=dict(gridcolor='rgba(255,255,255,0.04)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.04)', title=metrik_birim[metrik]),
        font=dict(color='#94a3b8', family='Inter'),
        hovermode='x unified',
        legend=dict(
            orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1,
            bgcolor='rgba(0,0,0,0)', font=dict(color='#94a3b8')
        ),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Özet tablo
    if ozet_veriler:
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("📋", "İstatistik Özeti", f"{metrik_baslik[metrik]} — Seçili cihazların karşılaştırmalı özeti")
        
        kpi_items = []
        for oz in ozet_veriler:
            kpi_items.append({
                "value": f"{oz['Ortalama']} {metrik_birim[metrik]}",
                "label": f"{oz['Cihaz']} Ort.",
                "color": colors[ozet_veriler.index(oz) % len(colors)]
            })
        kpi_row(kpi_items)

        st.markdown("<br>", unsafe_allow_html=True)
        df_ozet = pd.DataFrame(ozet_veriler).set_index("Cihaz")
        st.dataframe(df_ozet, use_container_width=True)
else:
    st.markdown("""<div class="glossy-card" style="text-align:center;"><div style="font-size:2rem; margin-bottom:8px;">📊</div><div style="font-size:1rem; color:#94a3b8; font-family:Inter,sans-serif;">Karşılaştırmak için en az bir cihaz seçin.</div></div>""", unsafe_allow_html=True)
