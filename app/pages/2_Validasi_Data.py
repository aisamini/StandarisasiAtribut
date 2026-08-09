"""Halaman Validasi Data: baca file DBF/CSV lalu deteksi kolom IGT+level di dalamnya."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.core.igt_config import detect_igt_level_columns, load_igt_list
from app.core.io_utils import DataReadError, read_attribute_table

st.set_page_config(page_title="Validasi Data - IGT P4T", page_icon="🔍", layout="wide")

st.title("Validasi Data")
st.write(
    "Unggah file atribut data spasial IGT P4T (.dbf atau .csv) untuk diperiksa apakah "
    "kolomnya dikenali sebagai kolom IGT+level yang valid (sesuai Permen ATR No. 1 "
    "Tahun 2025). Untuk shapefile (.shp), unggah langsung file .dbf pendampingnya."
)

uploaded_file = st.file_uploader("Pilih file data atribut (.dbf/.csv)", type=["dbf", "csv"])

if uploaded_file is not None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / uploaded_file.name
        tmp_path.write_bytes(uploaded_file.getvalue())

        try:
            df = read_attribute_table(tmp_path)
        except DataReadError as exc:
            st.error(f"Gagal membaca file: {exc}")
        else:
            igt_list = load_igt_list()
            matches = detect_igt_level_columns(df.columns, igt_list)

            if not matches:
                known_prefixes = ", ".join(f"{item['prefix']} ({item['nama_igt']})" for item in igt_list)
                st.error(
                    "Tidak ada kolom IGT+level yang dikenali di file ini. Kolom yang ditemukan: "
                    f"{', '.join(df.columns) if len(df.columns) else '(tidak ada)'}. "
                    f"Prefix IGT yang terdaftar: {known_prefixes}. Pastikan nama kolom persis "
                    "sesuai Permen (mis. 'ptnObjKC' + 'idptnObjKC')."
                )
            else:
                st.success(f"{len(matches)} kombinasi IGT+level terdeteksi. {len(df)} baris data ditemukan.")
                st.dataframe(
                    [
                        {
                            "Nama_IGT": m["nama_igt"],
                            "Level": m["level"],
                            "Kolom_Nama": m["name_col"],
                            "Kolom_Kode": m["code_col"],
                        }
                        for m in matches
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
                st.dataframe(df, use_container_width=True, hide_index=True)
