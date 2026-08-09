"""Halaman utama aplikasi validasi data spasial IGT P4T."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from app.core.rules_manager import get_active_rules_summary
from app.core.validator import (
    build_discrepancy_report_excel,
    run_validation_for_all_categories,
    save_validation_snapshot,
)

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

st.subheader("Ringkasan Hasil Validasi Data")
results, categories_missing_data, categories_missing_rules = run_validation_for_all_categories()
snapshot_path = save_validation_snapshot(results, categories_missing_data, categories_missing_rules)

if categories_missing_rules:
    st.warning(
        "Kategori berikut ditemukan di folder `data/` tetapi **belum punya ruleset "
        "sama sekali**. Unggah aturan untuk kategori ini di halaman **Kelola Aturan**: "
        f"{', '.join(categories_missing_rules)}."
    )

if categories_missing_data:
    st.info(
        "Kategori berikut sudah punya ruleset aktif tetapi belum ditemukan file data "
        f"yang cocok di folder `data/`: {', '.join(categories_missing_data)}."
    )

if not results:
    st.info("Belum ada hasil validasi. Pastikan ada file data di `data/` yang cocok dengan kategori beruleset aktif.")
else:
    st.caption(
        f"Hasil validasi beserta kandidat koreksi disimpan di `output/{snapshot_path.name}` "
        "untuk dipakai antarmuka koreksi."
    )
    st.download_button(
        label="Download Laporan Ringkasan Diskrepansi (Excel)",
        data=build_discrepancy_report_excel(results),
        file_name=f"laporan_diskrepansi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    for category, result in sorted(results.items()):
        with st.expander(
            f"{category}  —  {result.total_records} record  (file: {result.data_file})",
            expanded=True,
        ):
            if not result.attribute_results:
                st.write("Tidak ada atribut yang bisa dicocokkan untuk kategori ini.")
            else:
                summary_rows = []
                for attribute, attr_result in sorted(result.attribute_results.items()):
                    summary_rows.append(
                        {
                            "Nama_Atribut": attribute,
                            "Jumlah_Record_Salah": attr_result.error_count,
                            "Total_Record_Diperiksa": attr_result.total_checked,
                            "Persentase_Salah": (
                                f"{attr_result.error_count / attr_result.total_checked:.1%}"
                                if attr_result.total_checked
                                else "0.0%"
                            ),
                        }
                    )
                st.dataframe(
                    pd.DataFrame(summary_rows), use_container_width=True, hide_index=True
                )

                for attribute, attr_result in sorted(result.attribute_results.items()):
                    if not attr_result.invalid_value_counts:
                        continue
                    st.caption(f"Nilai tidak valid untuk atribut **{attribute}**:")
                    invalid_rows = []
                    for value, freq in sorted(
                        attr_result.invalid_value_counts.items(),
                        key=lambda kv: kv[1],
                        reverse=True,
                    ):
                        candidates = attr_result.suggestions.get(value, [])
                        candidates_str = (
                            ", ".join(
                                f"{c['nilai']} ({c['skor_persen']}%)" for c in candidates
                            )
                            if candidates
                            else "-"
                        )
                        invalid_rows.append(
                            {
                                "Nilai": value,
                                "Frekuensi": freq,
                                "Top-3 Kandidat Pengganti (skor)": candidates_str,
                            }
                        )
                    st.dataframe(
                        pd.DataFrame(invalid_rows), use_container_width=True, hide_index=True
                    )

            if result.attributes_not_in_data:
                st.warning(
                    "Atribut berikut ada di ruleset tapi tidak ditemukan kolomnya di data: "
                    f"{', '.join(result.attributes_not_in_data)}."
                )

st.divider()
st.write("Gunakan menu di sidebar untuk mengelola aturan atau menjalankan validasi data.")
