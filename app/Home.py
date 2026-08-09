"""Halaman utama aplikasi validasi data spasial IGT P4T."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.core.igt_config import get_igt_style, load_igt_list
from app.core.rules_manager import get_ruleset_summary
from app.core.validator import (
    build_discrepancy_report_excel,
    display_value,
    run_validation_over_data_folder,
    save_validation_snapshot,
)

st.set_page_config(page_title="Validasi Data Spasial IGT P4T", page_icon="🗺️", layout="wide")

st.title("Validasi Data Spasial IGT P4T")
st.write(
    "Aplikasi untuk memvalidasi atribut data spasial IGT P4T level **Rinci** "
    "(satu-satunya level yang ada di data lapangan) terhadap ruleset per IGT "
    "(nama kolom mengikuti Permen ATR No. 1 Tahun 2025)."
)

st.subheader("Ringkasan Ruleset per IGT")
ruleset_summary_df = get_ruleset_summary()
st.dataframe(ruleset_summary_df, use_container_width=True, hide_index=True)
if (ruleset_summary_df["Status"] == "Belum Ada").any():
    st.info("Ada IGT yang belum punya ruleset. Unggah lewat halaman **Kelola Aturan**.")

st.divider()

st.subheader("Ringkasan Hasil Validasi Data")
st.caption(
    "Semua file di folder `data/` digabung jadi satu dataset (kolom SUMBER_FILE "
    "menandai asal tiap baris) sebelum divalidasi. Untuk mengunggah banyak file "
    "sekaligus, gunakan halaman **Validasi Data**."
)

merged_df, result = run_validation_over_data_folder()
snapshot_path = save_validation_snapshot(result)

if result.total_records == 0:
    st.info("Belum ada file data di folder `data/` untuk divalidasi.")
else:
    st.write(f"Total **{result.total_records}** record dari **{len(result.sumber_files)}** file: {', '.join(result.sumber_files)}")
    st.caption(f"Snapshot hasil validasi disimpan di `output/{snapshot_path.name}`.")

    st.download_button(
        label="Download Laporan Ringkasan Diskrepansi (Excel, 2 sheet)",
        data=build_discrepancy_report_excel(result, merged_df),
        file_name=f"laporan_diskrepansi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    if not result.column_stats:
        st.warning(
            "Tidak ada kolom level Rinci (mis. 'ptnObjRI') yang dikenali di data manapun. "
            "Cek apakah nama kolom sudah sesuai prefix IGT yang terdaftar."
        )

    igt_list = load_igt_list()
    for cs in result.column_stats:
        icon, _bg, _fg = get_igt_style(cs.nama_igt, igt_list)
        with st.expander(f"{icon} {cs.nama_igt} — kolom `{cs.column}`", expanded=True):
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

st.divider()
st.write("Gunakan menu di sidebar untuk mengelola aturan atau menjalankan validasi/koreksi data.")
