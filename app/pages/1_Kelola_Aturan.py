"""Halaman Kelola Aturan: download template, upload, validasi, dan update ruleset per kategori."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import io

import pandas as pd
import streamlit as st

from app.core.rules_manager import (
    RulesValidationError,
    build_empty_template,
    get_active_rules_summary,
    save_archive_copy,
    update_active_rules,
    validate_columns,
)

st.set_page_config(page_title="Kelola Aturan - IGT P4T", page_icon="📋", layout="wide")

st.title("Kelola Aturan")
st.write(
    "Unduh template, unggah ruleset baru, dan pantau aturan atribut yang sedang aktif "
    "per kategori IGT."
)

st.subheader("1. Unduh Template")
st.write("Gunakan template ini agar format kolom sesuai dengan yang diharapkan sistem.")
st.download_button(
    label="Download Template Excel Kosong",
    data=build_empty_template(),
    file_name="template_aturan_igt_p4t.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

st.subheader("2. Upload Aturan Baru")
uploaded_file = st.file_uploader("Pilih file Excel (.xlsx) berisi aturan atribut", type=["xlsx"])

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
    except Exception as exc:  # noqa: BLE001 - tampilkan pesan apa adanya ke pengguna
        st.error(f"Gagal membaca file Excel: {exc}")
    else:
        try:
            validate_columns(df)
        except RulesValidationError as exc:
            st.error(str(exc))
        else:
            st.success("Format file valid dan sesuai template.")
            categories_in_file = sorted(df["Kategori_IGT"].astype(str).str.strip().unique())
            st.write(f"Kategori terdeteksi dalam file: {', '.join(categories_in_file)}")
            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("Simpan dan Terapkan Aturan", type="primary"):
                archive_path = save_archive_copy(file_bytes, uploaded_file.name)
                updated_categories = update_active_rules(df)
                st.success(
                    f"Aturan berhasil diperbarui untuk kategori: {', '.join(updated_categories)}. "
                    f"Arsip disimpan di rules/archive/{archive_path.name}."
                )
                st.rerun()

st.divider()

st.subheader("3. Aturan yang Sedang Aktif")
summary_df = get_active_rules_summary()
if summary_df.empty:
    st.info("Belum ada ruleset aktif untuk kategori manapun.")
else:
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
