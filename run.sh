#!/usr/bin/env bash
# Jalankan aplikasi cukup dengan: ./run.sh
set -e
cd "$(dirname "$0")"
pip install -r requirements.txt -q
streamlit run app/Home.py
