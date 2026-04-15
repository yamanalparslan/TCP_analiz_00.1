"""
Solar Monitor - Ana Giriş Noktası
===================================
Streamlit multipage uygulamasının giriş noktası.

Çalıştırma:
    streamlit run panel.py

Not: Bu dosya Streamlit'in multipage yapısı için
ana dizinde bulunmaktadır. Asıl panel panel.py'dir.
Doğrudan çalıştırmak için:
    streamlit run panel.py
"""

# panel.py Streamlit'in ana giriş noktasıdır.
# Bu dosya yalnızca uyumluluk için vardır.

import subprocess
import sys
import os

if __name__ == "__main__":
    panel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "panel.py")
    subprocess.run([sys.executable, "-m", "streamlit", "run", panel_path])
