"""Halaman Koreksi Data: pilih file data, tabel record salah (kode+nama), terapkan koreksi."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.config import OUTPUT_DIR
from app.core.igt_config import slugify
from app.core.io_utils import (
    DataReadError,
    DataWriteError,
    export_attribute_table_bytes,
    read_attribute_table,
    write_attribute_table,
)
from app.core.validator import build_ruleset_lookup, get_invalid_pair_records, list_data_files

st.set_page_config(page_title="Koreksi Data - IGT P4T", page_icon="🛠️", layout="wide")

st.title("Koreksi Data")
st.write(
    "Pilih file data, lalu untuk tiap record yang pasangan kode+nama-nya terdeteksi "
    "salah, pilih kandidat pengganti dari dropdown (atau ketik kode+nama lain secara "
    "manual), lalu klik **Terapkan Koreksi** untuk menyimpan perubahan ke data."
)

TIDAK_DIUBAH = "__tidak_diubah__"
INPUT_MANUAL = "__input_manual__"

data_files = list_data_files()
if not data_files:
    st.warning("Belum ada file data di folder `data/`.")
    st.stop()

data_path = st.selectbox("File Data", data_files, format_func=lambda p: p.name)

try:
    df = read_attribute_table(data_path)
except DataReadError as exc:
    st.error(f"Gagal membaca file data: {exc}")
    st.stop()

lookup = build_ruleset_lookup()
invalid_records = get_invalid_pair_records(df, lookup=lookup)

st.caption(f"File data: `{data_path.name}` — {len(df)} record total.")

export_suffix = ".dbf" if data_path.suffix.lower() in (".dbf", ".shp") else ".csv"
try:
    export_bytes = export_attribute_table_bytes(df, export_suffix)
    st.download_button(
        label=f"Download Data Terkoreksi ({export_suffix})",
        data=export_bytes,
        file_name=f"{slugify(data_path.stem)}_terkoreksi{export_suffix}",
        mime="application/octet-stream",
    )
except DataWriteError as exc:
    st.error(f"Gagal menyiapkan file unduhan: {exc}")

if not invalid_records:
    st.success(
        "Tidak ada record salah untuk kombinasi IGT+level yang punya ruleset aktif di file ini."
    )
    st.stop()

st.subheader(f"Record Salah ({len(invalid_records)})")

header = st.columns([2, 1, 1, 2, 3, 3])
header[0].markdown("**IGT / Level**")
header[1].markdown("**Baris**")
header[2].markdown("**Kode Saat Ini**")
header[3].markdown("**Nama Saat Ini**")
header[4].markdown("**Pilih Koreksi**")
header[5].markdown("**Input Manual (Kode / Nama)**")

for record in invalid_records:
    row = st.columns([2, 1, 1, 2, 3, 3])
    row[0].write(f"{record.nama_igt} / {record.level}")
    row[1].write(record.row_index + 1)
    row[2].write(record.current_kode)
    row[3].write(record.current_nama)

    record_key = f"{record.row_index}_{record.name_col}_{record.code_col}"

    option_values = [TIDAK_DIUBAH]
    option_display = {TIDAK_DIUBAH: "-- Tidak diubah --"}
    for c in record.candidates:
        val = f"{c['kode']}::{c['nama']}"
        option_values.append(val)
        option_display[val] = f"{c['kode']} - {c['nama']} ({c['skor_persen']}%)"
    option_values.append(INPUT_MANUAL)
    option_display[INPUT_MANUAL] = "Input manual lain"

    select_key = f"select_{record_key}"
    selection = row[4].selectbox(
        "Pilih koreksi",
        options=option_values,
        key=select_key,
        format_func=lambda v, option_display=option_display: option_display[v],
        label_visibility="collapsed",
    )

    if selection == INPUT_MANUAL:
        manual_cols = row[5].columns(2)
        manual_cols[0].text_input(
            "Kode manual", key=f"manual_kode_{record_key}", label_visibility="collapsed",
            placeholder="Kode",
        )
        manual_cols[1].text_input(
            "Nama manual", key=f"manual_nama_{record_key}", label_visibility="collapsed",
            placeholder="Nama",
        )
    else:
        row[5].write("")

st.divider()

if st.button("Terapkan Koreksi", type="primary"):
    corrected_df = df.copy()
    applied_count = 0
    skipped_incomplete_manual: list[str] = []

    for record in invalid_records:
        record_key = f"{record.row_index}_{record.name_col}_{record.code_col}"
        select_key = f"select_{record_key}"
        selection = st.session_state.get(select_key, TIDAK_DIUBAH)

        if selection == TIDAK_DIUBAH:
            continue

        if selection == INPUT_MANUAL:
            final_kode = st.session_state.get(f"manual_kode_{record_key}", "").strip()
            final_nama = st.session_state.get(f"manual_nama_{record_key}", "").strip()
            if not final_kode or not final_nama:
                skipped_incomplete_manual.append(
                    f"baris {record.row_index + 1} ({record.nama_igt}/{record.level})"
                )
                continue
        else:
            final_kode, final_nama = selection.split("::", 1)

        corrected_df.at[record.row_index, record.code_col] = final_kode
        corrected_df.at[record.row_index, record.name_col] = final_nama
        applied_count += 1

    if applied_count == 0:
        if skipped_incomplete_manual:
            st.warning(
                "Tidak ada koreksi yang diterapkan. Baris berikut dilewati karena input "
                f"manual (kode/nama) belum lengkap: {', '.join(skipped_incomplete_manual)}."
            )
        else:
            st.warning("Tidak ada koreksi yang dipilih. Pilih kandidat atau isi input manual terlebih dahulu.")
    else:
        try:
            saved_path = write_attribute_table(data_path, corrected_df)
            st.success(f"{applied_count} koreksi berhasil diterapkan dan disimpan ke `{saved_path.name}`.")
        except DataWriteError:
            fallback_path = OUTPUT_DIR / f"{slugify(data_path.stem)}_terkoreksi.csv"
            saved_path = write_attribute_table(fallback_path, corrected_df)
            st.success(
                f"{applied_count} koreksi diterapkan. Format asli ({data_path.suffix}) tidak bisa "
                f"ditulis langsung, hasil koreksi disimpan sebagai `output/{saved_path.name}`."
            )

        if skipped_incomplete_manual:
            st.warning(
                "Baris berikut dilewati karena input manual (kode/nama) belum lengkap: "
                f"{', '.join(skipped_incomplete_manual)}."
            )

        for record in invalid_records:
            record_key = f"{record.row_index}_{record.name_col}_{record.code_col}"
            st.session_state.pop(f"select_{record_key}", None)
            st.session_state.pop(f"manual_kode_{record_key}", None)
            st.session_state.pop(f"manual_nama_{record_key}", None)

        st.rerun()
