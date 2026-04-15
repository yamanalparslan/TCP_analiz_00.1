"""
Solar Monitor - Kimlik Doğrulama Sistemi
==========================================
Streamlit session state tabanlı login/logout.
Glossy tasarımlı giriş ekranı.

Kullanım:
    from auth import check_auth, logout_button
    if not check_auth():
        st.stop()
    logout_button()
"""

import os
import hashlib
import streamlit as st


def _get_password_hash(password: str) -> str:
    """SHA-256 ile şifre hash'i oluşturur."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _verify_password(password: str, stored_hash: str) -> bool:
    """Şifreyi hash ile karşılaştırır."""
    return _get_password_hash(password) == stored_hash


def _is_auth_enabled() -> bool:
    """Authentication aktif mi kontrol eder."""
    return os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")


def _get_credentials() -> tuple[str, str]:
    """Kullanıcı adı ve şifre hash'ini döner.
    
    Returns:
        (username, password_hash) — hash boşsa varsayılan 'admin' şifresi kullanılır
    """
    username = os.getenv("AUTH_USERNAME", "admin")
    password_hash = os.getenv("AUTH_PASSWORD_HASH", "")

    # Hash tanımlı değilse varsayılan şifre: "admin"
    if not password_hash:
        password_hash = _get_password_hash("admin")

    return username, password_hash


# ══════════════════════════════════════════════════════════════
# LOGIN CSS (Glossy Tasarım)
# ══════════════════════════════════════════════════════════════
_LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

.login-container {
    max-width: 420px;
    margin: 60px auto;
    padding: 0;
}
.login-card {
    background: linear-gradient(145deg, 
        rgba(30, 41, 59, 0.85) 0%, 
        rgba(15, 23, 42, 0.7) 100%);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 20px;
    padding: 40px 36px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.06);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    position: relative;
    overflow: hidden;
}
.login-card::before {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 3px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6, #a855f7);
}
.login-logo {
    text-align: center;
    margin-bottom: 8px;
    font-size: 3rem;
}
.login-title {
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 1.5rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1, #a855f7);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 4px;
}
.login-subtitle {
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 0.85rem;
    color: #64748b;
    margin-bottom: 28px;
}
.login-footer {
    text-align: center;
    font-family: 'Inter', sans-serif;
    font-size: 0.75rem;
    color: #475569;
    margin-top: 20px;
}
</style>
"""


def check_auth() -> bool:
    """Kimlik doğrulama kontrolü.

    Auth devre dışıysa True döner.
    Giriş yapılmışsa True döner.
    Giriş yapılmamışsa login formu gösterir ve False döner.
    """
    if not _is_auth_enabled():
        return True

    # Zaten giriş yapılmış mı?
    if st.session_state.get("authenticated"):
        return True

    # Login ekranını göster
    _show_login_form()
    return False


def _show_login_form():
    """Glossy login formu gösterir."""
    # Arka plan ve login CSS
    st.markdown("""
    <style>
    .stApp {
        background: 
            radial-gradient(ellipse at 20% 50%, rgba(99, 102, 241, 0.1) 0%, transparent 50%),
            radial-gradient(ellipse at 80% 20%, rgba(168, 85, 247, 0.08) 0%, transparent 50%),
            #0a0e1a !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="login-container">
        <div class="login-card">
            <div class="login-logo">⚡</div>
            <div class="login-title">Solar Monitor</div>
            <div class="login-subtitle">Güneş Enerjisi Santrali İzleme Sistemi</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Login formu (Streamlit native — CSS card'ın altına yerleşir)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            username_input = st.text_input("👤 Kullanıcı Adı", placeholder="admin")
            password_input = st.text_input("🔒 Şifre", type="password", placeholder="••••••")
            submitted = st.form_submit_button("🔓 Giriş Yap", width='stretch', type="primary")

            if submitted:
                expected_user, expected_hash = _get_credentials()

                if username_input == expected_user and _verify_password(password_input, expected_hash):
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = username_input
                    st.rerun()
                else:
                    st.error("❌ Kullanıcı adı veya şifre hatalı!")

        st.markdown("""
        <div class="login-footer">
            Varsayılan: admin / admin<br>
            .env dosyasından değiştirilebilir.
        </div>
        """, unsafe_allow_html=True)


def logout_button():
    """Sidebar'da çıkış butonu gösterir."""
    if not _is_auth_enabled():
        return

    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.markdown("---")
            user = st.session_state.get("username", "admin")
            st.caption(f"👤 {user}")
            if st.button("🚪 Çıkış Yap", key="logout_btn"):
                st.session_state["authenticated"] = False
                st.session_state.pop("username", None)
                st.rerun()


def get_current_user() -> str:
    """Mevcut oturumdaki kullanıcı adını döner."""
    return st.session_state.get("username", "admin")
