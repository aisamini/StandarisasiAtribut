"""Halaman Kelola Aturan: pilih IGT, pakai klasifikasi resmi ATAU upload aturan kustom."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import io

import pandas as pd
import streamlit as st

from app.core.igt_config import IgtConfigError, add_igt, get_prefix, get_ri_column, load_igt_list, slugify
from app.core.rules_manager import (
    RulesValidationError,
    apply_preset,
    build_template_for_igt,
    get_preset_preview,
    get_ruleset_summary,
    list_presets,
    save_archive_copy,
    update_active_ruleset,
    validate_ruleset_columns,
)

st.set_page_config(page_title="Kelola Aturan - IGT P4T", page_icon="📋", layout="wide")

st.title("Kelola Aturan")
st.write(
    "Halaman ini untuk mengatur aturan/klasifikasi acuan tiap IGT. Kalau ingin memakai "
    "klasifikasi resmi (Juknis/Permen) yang berlaku, pakai tab **Gunakan Klasifikasi "
    "Resmi**. Tab **Upload Aturan Kustom** hanya diperlukan kalau ada revisi atau aturan "
    "baru yang belum tersedia di daftar resmi."
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

tab_resmi, tab_upload = st.tabs(["🏛️ Gunakan Klasifikasi Resmi", "📤 Upload Aturan Kustom"])

with tab_resmi:
    presets = list_presets(nama_igt)

    if not presets:
        st.info(
            f"Belum ada klasifikasi resmi bawaan untuk **{nama_igt}**. Taruh file Excel-nya "
            f"di folder `rules/presets/{slugify(nama_igt)}/` (lihat README bagian "
            "'Klasifikasi Resmi Bawaan'), atau pakai tab **Upload Aturan Kustom** sebagai "
            "gantinya untuk sekarang."
        )
    else:
        preset_by_label = {p["label"]: p["filename"] for p in presets}
        selected_label = st.selectbox(
            "Pilih Klasifikasi Resmi",
            list(preset_by_label.keys()),
            key=f"preset_select_{nama_igt}",
        )
        selected_filename = preset_by_label[selected_label]

        try:
            preview = get_preset_preview(nama_igt, selected_filename)
        except RulesValidationError as exc:
            st.error(f"File preset '{selected_filename}' bermasalah: {exc}")
        except Exception as exc:  # noqa: BLE001 - tampilkan pesan apa adanya ke pengguna
            st.error(f"Gagal membaca file preset '{selected_filename}': {exc}")
        else:
            st.caption(
                f"File: `{selected_filename}` — kolom `{preview['kolom']}` ditemukan, "
                f"**{preview['jumlah_nilai_valid']}** nilai valid unik dari "
                f"{preview['jumlah_baris']} baris data."
            )

            if st.button("Terapkan Klasifikasi Resmi", type="primary", key=f"apply_preset_{nama_igt}"):
                archive_path, _active_path = apply_preset(nama_igt, selected_filename)
                st.success(
                    f"Ruleset untuk **{nama_igt}** berhasil diperbarui memakai "
                    f"**{selected_label}** (ruleset lama diarsipkan otomatis ke "
                    f"rules/archive/{archive_path.name})."
                )
                st.rerun()

with tab_upload:
    st.write(
        "Unduh template kolom Rinci-nya, lalu unggah daftar nilai valid untuk IGT ini. "
        "Sistem hanya mencari SATU kolom yang relevan (nama kolom tidak case-sensitive) "
        "— kolom lain di file yang diunggah (mis. NO_URUT, WADMKK) diabaikan, bukan "
        "dianggap error. Upload baru untuk IGT yang sama akan MENGGANTI SELURUH ruleset "
        "IGT itu."
    )

    st.subheader("Unduh Template")
    st.write(f"Template berisi 1 kolom Rinci baku untuk **{nama_igt}**: `{get_ri_column(get_prefix(nama_igt))}`.")
    st.download_button(
        label=f"Download Template Excel — {nama_igt}",
        data=build_template_for_igt(nama_igt),
        file_name=f"template_ruleset_{nama_igt.replace(' ', '_')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.subheader("Upload Ruleset")
    uploaded_file = st.file_uploader(
        f"Pilih file Excel (.xlsx) berisi daftar nilai valid untuk {nama_igt}",
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
                found_column = validate_ruleset_columns(df, nama_igt)
            except RulesValidationError as exc:
                st.error(str(exc))
            else:
                st.success(f"Kolom '{found_column}' ditemukan dan akan dipakai sebagai daftar nilai valid.")
                st.dataframe(df, use_container_width=True, hide_index=True)

                if st.button("Simpan dan Terapkan Ruleset", type="primary"):
                    archive_path = save_archive_copy(file_bytes, nama_igt, uploaded_file.name)
                    update_active_ruleset(nama_igt, df, found_column)
                    st.success(
                        f"Ruleset untuk **{nama_igt}** berhasil diperbarui (menggantikan ruleset lama). "
                        f"Arsip disimpan di rules/archive/{archive_path.name}."
                    )
                    st.rerun()

st.divider()

st.subheader("2. Ringkasan Ruleset per IGT")
summary_df = get_ruleset_summary()
st.dataframe(summary_df, use_container_width=True, hide_index=True)
