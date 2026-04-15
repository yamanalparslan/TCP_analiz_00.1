import streamlit as st
import time
import sys, os
from datetime import datetime
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import veritabani
from models import FAULT_MAP_189, FAULT_MAP_193
from styles import inject_glossy_css, section_header, alarm_card, badge, kpi_row
from auth import check_auth, logout_button

st.set_page_config(page_title="Aktif Alarmlar", page_icon="🚨", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()
veritabani.init_db()

st.title("⚠️ Aktif Donanım Arızaları")
section_header("🚨", "Canlı Alarm Paneli", "Cihazlardan gelen hata kodlarının (Register 189 & 193) detaylı dökümü")

col_r, col_t = st.columns([1, 3])
with col_r:
    auto_refresh = st.toggle("🔄 Otomatik Yenileme (10s)", value=False)
with col_t:
    if st.button("🔄 Şimdi Yenile"):
        st.rerun()
    st.caption('Son güncelleme: ' + datetime.now().strftime('%H:%M:%S'))


def hata_bit_coz(kod, fault_map):
    hatalar = []
    for bit in range(32):
        if (kod >> bit) & 1:
            aciklama = fault_map.get(bit, "Bilinmeyen Hata (Bit " + str(bit) + ")")
            hatalar.append((bit, aciklama))
    return hatalar


durumlar = veritabani.tum_cihazlarin_son_durumu()

if not durumlar:
    st.warning("Henüz veri yok.")
else:
    hata_sayisi = 0
    temiz_sayisi = 0

    for row in durumlar:
        dev_id = row[0]
        h189 = row[6] if len(row) > 6 and row[6] else 0
        h193 = row[7] if len(row) > 7 and row[7] else 0
        has_error = (h189 != 0) or (h193 != 0)

        if has_error:
            hata_sayisi += 1
            hatalar_189 = hata_bit_coz(h189, FAULT_MAP_189)
            hatalar_193 = hata_bit_coz(h193, FAULT_MAP_193)

            parts = []
            parts.append('<div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">')
            parts.append('<span style="font-size:1.3rem;">🔴</span>')
            parts.append('<span style="font-size:1.1rem; font-weight:700; color:#fca5a5; font-family:Inter,sans-serif;">ID: ' + str(dev_id) + '</span>')
            parts.append(badge("ARIZA", "danger"))
            parts.append('</div>')

            if hatalar_189:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 189 Hataları:</div>')
                for bit, aciklama in hatalar_189:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;">• Bit ' + str(bit) + ': ' + aciklama + '</div>')
            if hatalar_193:
                parts.append('<div style="margin:8px 0 4px 0; font-weight:600; color:#f87171; font-family:Inter,sans-serif;">Register 193 Hataları:</div>')
                for bit, aciklama in hatalar_193:
                    parts.append('<div style="padding:3px 0 3px 16px; color:#fca5a5; font-size:0.9rem; font-family:Inter,sans-serif;">• Bit ' + str(bit) + ': ' + aciklama + '</div>')

            parts.append('<div style="margin-top:8px; font-size:0.75rem; color:#64748b; font-family:Inter,sans-serif;">Hex: R189=0x' + format(h189, "08X") + ' | R193=0x' + format(h193, "04X") + '</div>')
            alarm_card(dev_id, True, ''.join(parts))
        else:
            temiz_sayisi += 1
            content = '<div style="display:flex; align-items:center; gap:12px;"><span style="font-size:1.3rem;">✅</span><span style="font-size:1.05rem; font-weight:600; color:#6ee7b7; font-family:Inter,sans-serif;">ID: ' + str(dev_id) + ' — Sistem Stabil</span>' + badge("OK", "success") + '</div>'
            alarm_card(dev_id, False, content)

    st.markdown("---")
    kpi_row([
        {"value": str(len(durumlar)), "label": "Toplam Cihaz", "color": "#6366f1"},
        {"value": str(hata_sayisi), "label": "Arızalı", "color": "#ef4444"},
        {"value": str(temiz_sayisi), "label": "Sağlıklı", "color": "#10b981"},
    ])

    if hata_sayisi == 0:
        st.markdown('''
        <div class="glossy-card" style="text-align:center; margin-top:20px;">
            <div style="font-size:2rem; margin-bottom:8px;">🎉</div>
            <div style="font-size:1.1rem; font-weight:600; color:#6ee7b7; font-family:Inter,sans-serif;">
                Harika! Sistemde şu an hiç aktif arıza yok.
            </div>
        </div>
        ''', unsafe_allow_html=True)

if auto_refresh:
    time.sleep(10)
    st.rerun()
