@echo off
REM Jalankan aplikasi cukup dengan: klik dua kali file ini (run.bat)
cd /d "%~dp0"
pip install -r requirements.txt -q
streamlit run app/Home.py
