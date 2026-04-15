import streamlit as st
import sys, os, time, socket, subprocess
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from styles import inject_glossy_css, section_header, badge
from auth import check_auth, logout_button

st.set_page_config(page_title="Sanal İnverter", page_icon="🔌", layout="wide")
inject_glossy_css()
if not check_auth():
    st.stop()
logout_button()

st.title("🔌 Sanal İnverter (Simülatör)")
section_header("🤖", "Sistem Simülasyonu", "Fiziksel panellere bağlanmadan test verileri üretir")

def is_simulator_running():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('127.0.0.1', 5020)) == 0
    except:
        return False

# Session state initialization
if 'sim_process' not in st.session_state:
    st.session_state.sim_process = None

# Durum Barı
is_running = is_simulator_running()

col_status, col_action = st.columns([2, 1])

with col_status:
    if is_running:
        st.markdown(f'<div class="glossy-card" style="border-left: 4px solid #10b981; padding:20px;">'
                    f'<div style="font-size:1.4rem; color:#10b981; font-weight:700;">🟢 SİMÜLATÖR AKTİF</div>'
                    f'<div style="color:#94a3b8; margin-top:8px;">Sanal inverter arka planda başarıyla çalışıyor ve 5020 numaralı porttan Modbus TCP verisi yayınlıyor. Kolektör bu portu okuyabilir.</div>'
                    f'</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="glossy-card" style="border-left: 4px solid #ef4444; padding:20px;">'
                    f'<div style="font-size:1.4rem; color:#ef4444; font-weight:700;">🔴 SİMÜLATÖR KAPALI</div>'
                    f'<div style="color:#94a3b8; margin-top:8px;">Sistemde anlık olarak çalışan bir sanal inverter tespit edilemedi. Test verisi akışı durmuş durumda.</div>'
                    f'</div>', unsafe_allow_html=True)

with col_action:
    st.markdown("<br>", unsafe_allow_html=True)
    if not is_running:
        if st.button("▶️ Simülatörü Başlat", type="primary", use_container_width=True):
            script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'sanal_inverter.py'))
            try:
                if sys.platform == "win32":
                    st.session_state.sim_process = subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path), creationflags=subprocess.CREATE_NEW_CONSOLE)
                else:
                    st.session_state.sim_process = subprocess.Popen([sys.executable, script_path], cwd=os.path.dirname(script_path), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                st.success("Başlatıldı! Bağlantı kuruluyor...")
                time.sleep(2)
                st.rerun()
            except Exception as e:
                st.error(f"Başlatılamadı: {e}")
    else:
        if st.button("⏹️ Simülatörü Durdur", type="secondary", use_container_width=True):
            if st.session_state.sim_process:
                st.session_state.sim_process.terminate()
                st.session_state.sim_process = None
            else:
                # Eger bu oturumdan bagimsiz baslatildiysa socket / port uzerinden kill yapilmali
                # Bu ornekte sadece uygulama icinden baslatilanlar durdurulabilir.
                st.warning("Bu işlem manuel başlatıldığı için buradan durdurulamaz. Terminalden kapatın.")
            time.sleep(1)
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)
section_header("⚙️", "Simülasyon Detayları")

st.markdown("""
<div class="glossy-card" style="padding: 20px;">
    <h4>Simülatör Parametreleri</h4>
    <p style="color:#cbd5e1;">Arka planda çalışan <code>sanal_inverter.py</code> scripti, fiziki cihaz eksikliklerini örtmek için şu varsayılan değerleri simüle etmektedir:</p>
    <ul>
        <li><b>Bağlantı Modu:</b> Asenkron Modbus TCP (Port: 5020)</li>
        <li><b>Simüle Edilen Cihazlar (Slave ID):</b> 1, 2, 3</li>
        <li><b>Davranış Örüntüsü:</b> Gündüz gerçekçi gün ışığı (belli sıcaklıkta voltaj düşüşü)</li>
        <li><b>Hata Enjeksiyonu:</b> Rastgele Hata Kodu 189 ve Hata Kodu 193 simülasyonları</li>
        <li><b>Döngü Hızı:</b> Her 10 dakika, sistem için sanal 24 saati temsil eder! Gerçek hayattan çok daha ivmeli üretim yapar.</li>
    </ul>
    Eğer kolektör verileri okuyamıyorsa <i>Panel -> Ayarlar</i> sekmesinden IP adresini yapılandırdığınızdan emin olun (Docker için <code>solar-monitor</code>).
</div>
""", unsafe_allow_html=True)
