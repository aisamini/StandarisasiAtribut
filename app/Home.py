"""Halaman utama aplikasi validasi data spasial IGT P4T."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.core.rules_manager import get_active_rules_summary

st.set_page_config(page_title="Validasi Data Spasial IGT P4T", page_icon="🗺️", layout="wide")

st.title("Validasi Data Spasial IGT P4T")
st.write(
    "Aplikasi untuk memvalidasi atribut data spasial Informasi Geospasial Tematik "
    "Penatagunaan dan Penguasaan Tanah (IGT P4T) terhadap ruleset standar."
)

st.subheader("Ringkasan Aturan Aktif")
summary_df = get_active_rules_summary()
if summary_df.empty:
    st.info("Belum ada ruleset aktif. Silakan unggah aturan melalui halaman **Kelola Aturan**.")
else:
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

st.divider()
st.write("Gunakan menu di sidebar untuk mengelola aturan atau menjalankan validasi data.")
