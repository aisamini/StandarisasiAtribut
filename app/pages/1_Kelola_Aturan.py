"""Halaman Kelola Aturan: pilih IGT, download template, upload, validasi, dan ringkasan ruleset."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import io

import pandas as pd
import streamlit as st

from app.core.igt_config import IgtConfigError, add_igt, load_igt_list
from app.core.rules_manager import (
    RulesValidationError,
    build_template_for_igt,
    get_ruleset_summary,
    save_archive_copy,
    update_active_ruleset,
    validate_ruleset_columns,
)

st.set_page_config(page_title="Kelola Aturan - IGT P4T", page_icon="📋", layout="wide")

st.title("Kelola Aturan")
st.write(
    "Pilih IGT, unduh template kolomnya (sesuai Permen ATR No. 1 Tahun 2025), lalu "
    "unggah ruleset lengkap (4 level: Kecil/Menengah/Besar/Rinci) untuk IGT tersebut. "
    "Upload baru untuk IGT yang sama akan MENGGANTI SELURUH ruleset IGT itu."
)

TAMBAH_IGT_BARU = "+ Tambah IGT Baru"

st.subheader("1. Pilih IGT")
igt_list = load_igt_list()
igt_names = [item["nama_igt"] for item in igt_list]
pilihan = st.selectbox("IGT", [*igt_names, TAMBAH_IGT_BARU])

if pilihan == TAMBAH_IGT_BARU:
    with st.form("form_tambah_igt"):
        nama_igt_baru = st.text_input("Nama IGT baru", placeholder="mis. Perairan")
        prefix_baru = st.text_input(
            "Prefix kolom", placeholder="mis. par",
            help="Diawali huruf, hanya huruf/angka, tanpa spasi.",
        )
        submitted = st.form_submit_button("Tambahkan IGT", type="primary")

    if submitted:
        try:
            add_igt(nama_igt_baru, prefix_baru)
        except IgtConfigError as exc:
            st.error(str(exc))
        else:
            st.success(f"IGT '{nama_igt_baru.strip()}' berhasil ditambahkan.")
            st.rerun()

    st.stop()

nama_igt = pilihan

st.divider()

st.subheader("2. Unduh Template")
st.write(f"Template berisi 8 kolom baku untuk **{nama_igt}** (4 level, masing-masing kolom nama+kode).")
st.download_button(
    label=f"Download Template Excel — {nama_igt}",
    data=build_template_for_igt(nama_igt),
    file_name=f"template_ruleset_{nama_igt.replace(' ', '_')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

st.divider()

st.subheader("3. Upload Ruleset")
uploaded_file = st.file_uploader(
    f"Pilih file Excel (.xlsx) berisi ruleset lengkap untuk {nama_igt}",
    type=["xlsx"],
    key=f"uploader_{nama_igt}",
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()
    try:
        df = pd.read_excel(io.BytesIO(file_bytes), dtype=str)
    except Exception as exc:  # noqa: BLE001 - tampilkan pesan apa adanya ke pengguna
        st.error(f"Gagal membaca file Excel: {exc}")
    else:
        try:
            validate_ruleset_columns(df, nama_igt)
        except RulesValidationError as exc:
            st.error(str(exc))
        else:
            st.success("Format file valid dan sesuai template.")
            st.dataframe(df, use_container_width=True, hide_index=True)

            if st.button("Simpan dan Terapkan Ruleset", type="primary"):
                archive_path = save_archive_copy(file_bytes, nama_igt, uploaded_file.name)
                update_active_ruleset(nama_igt, df)
                st.success(
                    f"Ruleset untuk **{nama_igt}** berhasil diperbarui (menggantikan ruleset lama). "
                    f"Arsip disimpan di rules/archive/{archive_path.name}."
                )
                st.rerun()

st.divider()

st.subheader("4. Ringkasan Ruleset per IGT")
summary_df = get_ruleset_summary()
st.dataframe(summary_df, use_container_width=True, hide_index=True)
