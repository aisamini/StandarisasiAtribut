"""Halaman utama aplikasi validasi data spasial IGT P4T."""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st

from app.core.rules_manager import get_ruleset_summary
from app.core.validator import (
    build_discrepancy_report_excel,
    run_validation_for_all_data_files,
    save_validation_snapshot,
)

st.set_page_config(page_title="Validasi Data Spasial IGT P4T", page_icon="🗺️", layout="wide")

st.title("Validasi Data Spasial IGT P4T")
st.write(
    "Aplikasi untuk memvalidasi atribut data spasial Informasi Geospasial Tematik "
    "Penatagunaan dan Penguasaan Tanah (IGT P4T) terhadap ruleset standar per IGT "
    "(nama kolom mengikuti Permen ATR No. 1 Tahun 2025)."
)

st.subheader("Ringkasan Ruleset per IGT")
ruleset_summary_df = get_ruleset_summary()
st.dataframe(ruleset_summary_df, use_container_width=True, hide_index=True)
if (ruleset_summary_df["Status"] == "Belum Ada").any():
    st.info("Ada IGT yang belum punya ruleset. Unggah lewat halaman **Kelola Aturan**.")

st.divider()

st.subheader("Ringkasan Hasil Validasi Data")
results = run_validation_for_all_data_files()
snapshot_path = save_validation_snapshot(results)

if not results:
    st.info("Belum ada file data di folder `data/` untuk divalidasi.")
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

    for result in results:
        if result.unmatched:
            with st.expander(f"{result.data_file}  —  {result.total_records} record", expanded=False):
                st.warning(
                    "Tidak ada kolom IGT+level yang dikenali di file ini (cek prefix kolom "
                    "sesuai Permen)."
                )
            continue

        with st.expander(f"{result.data_file}  —  {result.total_records} record", expanded=True):
            for lr in result.level_results:
                st.markdown(f"**{lr.nama_igt} / Level {lr.level}**")

                if not lr.ruleset_tersedia:
                    st.warning(
                        f"IGT '{lr.nama_igt}' belum punya ruleset aktif — seluruh {lr.total_records} "
                        "record di level ini belum bisa divalidasi. Unggah rulesetnya di "
                        "halaman **Kelola Aturan**."
                    )
                    continue

                persentase = f"{lr.error_count / lr.total_records:.1%}" if lr.total_records else "0.0%"
                st.write(f"Jumlah record salah: **{lr.error_count}** dari {lr.total_records} ({persentase})")

                if lr.invalid_pair_counts:
                    invalid_rows = []
                    for key, freq in sorted(
                        lr.invalid_pair_counts.items(), key=lambda kv: kv[1], reverse=True
                    ):
                        kode, _, nama = key.partition("||")
                        candidates = lr.suggestions.get(key, [])
                        candidates_str = (
                            ", ".join(
                                f"{c['kode']} - {c['nama']} ({c['skor_persen']}%)" for c in candidates
                            )
                            if candidates
                            else "-"
                        )
                        invalid_rows.append(
                            {
                                "Kode": kode,
                                "Nama": nama,
                                "Frekuensi": freq,
                                "Top-3 Kandidat Pengganti (skor)": candidates_str,
                            }
                        )
                    st.dataframe(invalid_rows, use_container_width=True, hide_index=True)

                st.divider()

st.divider()
st.write("Gunakan menu di sidebar untuk mengelola aturan atau menjalankan validasi data.")
