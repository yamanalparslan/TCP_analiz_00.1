import streamlit as st
import pandas as pd
import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from styles import inject_glossy_css, section_header
from auth import check_auth, logout_button

st.set_page_config(page_title="Audit Log", page_icon="📝", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()
veritabani.init_db()
st.title("📝 Audit Log")
section_header("🔒", "İşlem Geçmişi", "Ayar değişiklikleri ve kullanıcı işlemleri")

limit = st.slider("Limit:", 10, 500, 100)
loglar = veritabani.audit_log_getir(limit=limit)
if loglar:
    df = pd.DataFrame(loglar, columns=["ID", "Kullanıcı", "İşlem", "Detay", "Zaman"]).drop(columns=["ID"])
    st.dataframe(df, width='stretch')
else:
    st.markdown('<div class="glossy-card" style="text-align:center;"><div style="font-size:2rem;margin-bottom:8px;">📋</div><div style="font-size:1rem;color:#94a3b8;font-family:Inter,sans-serif;">İşlem geçmişi yok.</div></div>', unsafe_allow_html=True)
