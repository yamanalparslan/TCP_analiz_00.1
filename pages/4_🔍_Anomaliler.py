import streamlit as st
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from styles import inject_glossy_css, section_header, anomaly_card, badge, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Anomaliler", page_icon="🔍", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()
veritabani.init_db()
st.title("🔍 Anomali Tespitleri")
section_header("🧠", "Anomali Motoru", "Statik + dinamik istatistiksel tespit")

col1, col2 = st.columns([1, 1])
with col1:
    filtre = st.selectbox("Ciddiyet:", ["Hepsi", "critical", "warning"])
with col2:
    limit = st.slider("Limit:", 10, 500, 100)
cid = None if filtre == "Hepsi" else filtre
anomaliler = veritabani.anomalileri_getir(limit=limit, ciddiyet=cid)
if anomaliler:
    kritik = sum(1 for a in anomaliler if a[3] == "critical")
    uyari = sum(1 for a in anomaliler if a[3] == "warning")
    kpi_row([
        {"value": str(len(anomaliler)), "label": "Toplam", "color": "#6366f1"},
        {"value": str(kritik), "label": "Kritik", "color": "#ef4444"},
        {"value": str(uyari), "label": "Uyarı", "color": "#f59e0b"},
    ])
    st.markdown("<br>", unsafe_allow_html=True)
    for a in anomaliler:
        a_id, a_sid, a_tip, a_cid, a_mesaj, a_zaman = a
        icon = "🔴" if a_cid == "critical" else "🟡"
        b = badge(a_cid.upper(), "danger" if a_cid == "critical" else "warning")
        c = '<div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">'
        c += '<span>' + icon + '</span>'
        c += '<span style="font-weight:700;color:#f1f5f9;font-family:Inter,sans-serif;">ID: ' + str(a_sid) + '</span>'
        c += b
        c += '<span style="font-size:0.75rem;color:#64748b;margin-left:auto;font-family:Inter,sans-serif;">' + str(a_zaman) + '</span></div>'
        c += '<div style="color:#cbd5e1;font-size:0.9rem;font-family:Inter,sans-serif;padding-left:28px;">' + str(a_mesaj) + '</div>'
        c += '<div style="color:#475569;font-size:0.75rem;font-family:Inter,sans-serif;padding-left:28px;margin-top:4px;">Tip: ' + str(a_tip) + '</div>'
        anomaly_card(a_cid, c)
else:
    st.markdown('<div class="glossy-card" style="text-align:center;"><div style="font-size:2rem;margin-bottom:8px;">✨</div><div style="font-size:1rem;color:#94a3b8;font-family:Inter,sans-serif;">Anomali kaydı yok.</div></div>', unsafe_allow_html=True)
