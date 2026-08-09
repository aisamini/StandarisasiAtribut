"""Halaman Validasi Data: upload banyak file sekaligus, gabungkan, lalu validasi level Rinci."""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.core.rules_manager import build_ri_ruleset_lookup
from app.core.validator import (
    build_discrepancy_report_excel,
    display_value,
    list_data_files,
    load_and_merge_data_files,
    validate_merged_dataframe,
)

st.set_page_config(page_title="Validasi Data - IGT P4T", page_icon="🔍", layout="wide")

st.title("Validasi Data")
st.write(
    "Unggah banyak file data spasial sekaligus (Excel/.xlsx, DBF/.dbf, atau .csv) — "
    "semua file akan digabung jadi satu dataset (kolom **SUMBER_FILE** menandai asal "
    "tiap baris untuk pelacakan), lalu divalidasi level Rinci sekaligus. Hasil ini "
    "sifatnya sementara (tidak disimpan ke folder `data/`) — untuk validasi yang "
    "otomatis terpantau di Home, letakkan file di folder `data/` langsung."
)

uploaded_files = st.file_uploader(
    "Pilih file data (bisa lebih dari satu)",
    type=["xlsx", "dbf", "csv"],
    accept_multiple_files=True,
)

if uploaded_files:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_paths = []
        for uploaded_file in uploaded_files:
            tmp_path = Path(tmp_dir) / uploaded_file.name
            tmp_path.write_bytes(uploaded_file.getvalue())
            tmp_paths.append(tmp_path)

        merged_df = load_and_merge_data_files(tmp_paths)

    if merged_df.empty:
        st.error("Tidak ada file yang berhasil dibaca. Cek format file yang diunggah.")
        st.stop()

    st.success(
        f"{len(uploaded_files)} file digabung jadi **{len(merged_df)}** record: "
        f"{', '.join(sorted(merged_df['SUMBER_FILE'].unique()))}."
    )

    ri_lookup = build_ri_ruleset_lookup()
    result = validate_merged_dataframe(merged_df, ri_lookup=ri_lookup)

    if not result.column_stats:
        st.warning(
            "Tidak ada kolom level Rinci (mis. 'ptnObjRI') yang dikenali di file yang diunggah. "
            "Cek apakah nama kolom sudah sesuai prefix IGT yang terdaftar."
        )
        st.stop()

    st.download_button(
        label="Download Laporan Ringkasan Diskrepansi (Excel, 2 sheet)",
        data=build_discrepancy_report_excel(result, merged_df),
        file_name=f"laporan_diskrepansi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    for cs in result.column_stats:
        with st.expander(f"{cs.nama_igt} — kolom `{cs.column}`", expanded=True):
            if not cs.ruleset_tersedia:
                st.warning(
                    f"IGT '{cs.nama_igt}' belum punya ruleset aktif — seluruh {cs.total_checked} "
                    "record belum bisa divalidasi. Unggah rulesetnya di halaman **Kelola Aturan**."
                )
                continue

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Record", cs.total_checked)
            col2.metric("Cocok / Valid", cs.valid_count)
            col3.metric("Salah Total", cs.salah_total_count)
            col4.metric("Typo", cs.typo_count)

            if cs.unique_value_info:
                rows = []
                for value, info in sorted(
                    cs.unique_value_info.items(), key=lambda kv: kv[1]["frekuensi"], reverse=True
                ):
                    candidates_str = (
                        ", ".join(f"{c['nilai']} ({c['skor_persen']}%)" for c in info["kandidat"])
                        if info["kandidat"]
                        else "-"
                    )
                    rows.append(
                        {
                            "Nilai": display_value(value),
                            "Frekuensi": info["frekuensi"],
                            "Kategori": info["kategori"],
                            "Top-5 Kandidat (Typo saja)": candidates_str,
                        }
                    )
                st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    existing = list_data_files()
    if existing:
        st.info(
            f"Folder `data/` sudah berisi {len(existing)} file "
            f"({', '.join(p.name for p in existing)}) — lihat halaman **Home** untuk "
            "hasil validasinya, atau **Koreksi Data** untuk membetulkannya."
        )
