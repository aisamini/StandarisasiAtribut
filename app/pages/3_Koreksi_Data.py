"""Halaman Koreksi Data: tabel record salah, pilih kandidat pengganti, terapkan ke data."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.config import OUTPUT_DIR
from app.core.io_utils import (
    DataReadError,
    DataWriteError,
    export_attribute_table_bytes,
    read_attribute_table,
    write_attribute_table,
)
from app.core.rules_manager import _slugify, get_active_categories
from app.core.validator import (
    _find_data_file_for_category,
    build_rules_lookup,
    get_invalid_records,
)

st.set_page_config(page_title="Koreksi Data - IGT P4T", page_icon="🛠️", layout="wide")

st.title("Koreksi Data")
st.write(
    "Pilih kategori, lalu untuk tiap record yang terdeteksi salah pilih kandidat "
    "pengganti dari dropdown (atau ketik nilai lain secara manual), lalu klik "
    "**Terapkan Koreksi** untuk menyimpan perubahan ke data."
)

TIDAK_DIUBAH = "-- Tidak diubah --"
INPUT_MANUAL = "Input manual lain"

categories = get_active_categories()
if not categories:
    st.warning("Belum ada ruleset aktif. Tambahkan aturan di halaman **Kelola Aturan** terlebih dahulu.")
    st.stop()

category = st.selectbox("Kategori IGT", categories)

data_path = _find_data_file_for_category(category)
if data_path is None:
    st.info(f"Tidak ditemukan file data di `data/` yang cocok untuk kategori **{category}**.")
    st.stop()

try:
    df = read_attribute_table(data_path)
except DataReadError as exc:
    st.error(f"Gagal membaca file data: {exc}")
    st.stop()

lookup = build_rules_lookup()
invalid_records = get_invalid_records(df, category, lookup)

st.caption(f"File data: `{data_path.name}` — {len(df)} record total.")

export_suffix = ".dbf" if data_path.suffix.lower() in (".dbf", ".shp") else ".csv"
try:
    export_bytes = export_attribute_table_bytes(df, export_suffix)
    st.download_button(
        label=f"Download Data Terkoreksi ({export_suffix})",
        data=export_bytes,
        file_name=f"{_slugify(category)}_terkoreksi{export_suffix}",
        mime="application/octet-stream",
    )
except DataWriteError as exc:
    st.error(f"Gagal menyiapkan file unduhan: {exc}")

if not invalid_records:
    st.success(f"Tidak ada record salah untuk kategori **{category}**. Semua nilai atribut sudah valid.")
    st.stop()

st.subheader(f"Record Salah ({len(invalid_records)})")

header = st.columns([1, 2, 3, 3, 3])
header[0].markdown("**Baris**")
header[1].markdown("**Atribut**")
header[2].markdown("**Nilai Saat Ini**")
header[3].markdown("**Pilih Koreksi**")
header[4].markdown("**Input Manual**")

for record in invalid_records:
    row = st.columns([1, 2, 3, 3, 3])
    row[0].write(record.row_index + 1)
    row[1].write(record.attribute)
    row[2].write(record.current_value)

    score_map = {c["nilai"]: c["skor_persen"] for c in record.candidates}
    options = [TIDAK_DIUBAH, *[c["nilai"] for c in record.candidates], INPUT_MANUAL]
    select_key = f"select_{record.row_index}_{record.attribute}"

    selection = row[3].selectbox(
        "Pilih koreksi",
        options=options,
        key=select_key,
        format_func=lambda v, score_map=score_map: (
            f"{v} ({score_map[v]}%)" if v in score_map else v
        ),
        label_visibility="collapsed",
    )

    manual_key = f"manual_{record.row_index}_{record.attribute}"
    if selection == INPUT_MANUAL:
        row[4].text_input(
            "Nilai manual", key=manual_key, label_visibility="collapsed",
            placeholder="Ketik nilai koreksi",
        )
    else:
        row[4].write("")

st.divider()

if st.button("Terapkan Koreksi", type="primary"):
    corrected_df = df.copy()
    applied_count = 0
    skipped_empty_manual: list[str] = []

    for record in invalid_records:
        select_key = f"select_{record.row_index}_{record.attribute}"
        selection = st.session_state.get(select_key, TIDAK_DIUBAH)

        if selection == TIDAK_DIUBAH:
            continue

        if selection == INPUT_MANUAL:
            manual_key = f"manual_{record.row_index}_{record.attribute}"
            final_value = st.session_state.get(manual_key, "").strip()
            if not final_value:
                skipped_empty_manual.append(f"baris {record.row_index + 1} ({record.attribute})")
                continue
        else:
            final_value = selection

        corrected_df.at[record.row_index, record.attribute] = final_value
        applied_count += 1

    if applied_count == 0:
        if skipped_empty_manual:
            st.warning(
                "Tidak ada koreksi yang diterapkan. Baris berikut dilewati karena input manual "
                f"kosong: {', '.join(skipped_empty_manual)}."
            )
        else:
            st.warning("Tidak ada koreksi yang dipilih. Pilih kandidat atau isi input manual terlebih dahulu.")
    else:
        try:
            saved_path = write_attribute_table(data_path, corrected_df)
            st.success(f"{applied_count} koreksi berhasil diterapkan dan disimpan ke `{saved_path.name}`.")
        except DataWriteError:
            fallback_path = OUTPUT_DIR / f"{_slugify(category)}_terkoreksi.csv"
            saved_path = write_attribute_table(fallback_path, corrected_df)
            st.success(
                f"{applied_count} koreksi diterapkan. Format asli ({data_path.suffix}) tidak bisa "
                f"ditulis langsung, hasil koreksi disimpan sebagai `output/{saved_path.name}`."
            )

        if skipped_empty_manual:
            st.warning(
                "Baris berikut dilewati karena input manual kosong: "
                f"{', '.join(skipped_empty_manual)}."
            )

        for record in invalid_records:
            st.session_state.pop(f"select_{record.row_index}_{record.attribute}", None)
            st.session_state.pop(f"manual_{record.row_index}_{record.attribute}", None)

        st.rerun()
