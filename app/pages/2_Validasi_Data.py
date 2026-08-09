"""Halaman Validasi Data: baca file DBF/SHP/CSV lalu validasi struktur kolom dasarnya."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.core.io_utils import (
    ColumnStructureError,
    DataReadError,
    load_and_validate_attribute_table,
)
from app.core.rules_manager import get_active_categories, get_expected_attributes

st.set_page_config(page_title="Validasi Data - IGT P4T", page_icon="🔍", layout="wide")

st.title("Validasi Data")
st.write(
    "Unggah file atribut data spasial IGT P4T (.dbf atau .csv) untuk diperiksa "
    "struktur kolomnya terhadap ruleset aktif. Untuk shapefile (.shp), unggah "
    "langsung file .dbf pendampingnya dari folder `data/`."
)

categories = get_active_categories()
if not categories:
    st.warning("Belum ada ruleset aktif. Tambahkan aturan di halaman **Kelola Aturan** terlebih dahulu.")
    st.stop()

category = st.selectbox("Kategori IGT", categories)
expected_columns = get_expected_attributes(category)
st.caption(f"Kolom yang diharapkan untuk kategori **{category}**: {', '.join(expected_columns)}")

uploaded_file = st.file_uploader(
    "Pilih file data atribut (.dbf/.csv)",
    type=["dbf", "csv"],
)

if uploaded_file is not None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / uploaded_file.name
        tmp_path.write_bytes(uploaded_file.getvalue())

        try:
            df = load_and_validate_attribute_table(tmp_path, expected_columns)
        except DataReadError as exc:
            st.error(f"Gagal membaca file: {exc}")
        except ColumnStructureError as exc:
            st.error(str(exc))
        else:
            st.success(f"Struktur kolom valid. {len(df)} baris data ditemukan.")
            st.dataframe(df, use_container_width=True, hide_index=True)
