import streamlit as st
import sys, os, platform
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from config import config
from styles import inject_glossy_css, section_header, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Sistem", page_icon="🖥️", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()
veritabani.init_db()
st.title("🖥️ Sistem Durumu")
section_header("⚙️", "Sistem Bilgileri", "Konfigürasyon ve ortam durumu")

kpi_row([
    {"value": platform.node()[:15], "label": "Hostname", "color": "#6366f1"},
    {"value": platform.python_version(), "label": "Python", "color": "#10b981"},
    {"value": platform.system(), "label": "OS", "color": "#f59e0b"},
])
st.markdown("<br>", unsafe_allow_html=True)

section_header("📡", "Modbus")
c1, c2, c3 = st.columns(3)
c1.metric("IP", config.MODBUS_IP)
c2.metric("Port", config.MODBUS_PORT)
c3.metric("Refresh", str(config.REFRESH_RATE) + "s")

section_header("📊", "Veritabanı")
try:
    import sqlite3
    conn = sqlite3.connect(config.DB_NAME)
    oc = conn.execute("SELECT COUNT(*) FROM olcumler").fetchone()[0]
    ac = conn.execute("SELECT COUNT(*) FROM anomaliler").fetchone()[0]
    sz = os.path.getsize(config.DB_NAME) if os.path.exists(config.DB_NAME) else 0
    conn.close()
    kpi_row([
        {"value": format(oc, ','), "label": "Ölçüm", "color": "#22d3ee"},
        {"value": format(ac, ','), "label": "Anomali", "color": "#f59e0b"},
        {"value": str(round(sz/1024)) + " KB", "label": "DB", "color": "#a855f7"},
    ])
except Exception as e:
    st.error("DB Hatası: " + str(e))

section_header("📢", "MQTT")
c1, c2 = st.columns(2)
c1.metric("MQTT", "✅ Aktif" if config.MQTT_ENABLED else "❌ Kapalı")
c2.metric("Broker", config.MQTT_HOST + ":" + str(config.MQTT_PORT))
