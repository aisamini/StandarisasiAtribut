"""Halaman Koreksi Data: koreksi per NILAI UNIK yang salah (bukan per baris), lalu verifikasi ulang.

Beroperasi di atas dataset kerja aktif di st.session_state (dibuat lewat halaman
Validasi Data, atau otomatis dimuat dari folder data/ kalau belum ada). Setelah
koreksi diterapkan, dataset kerja diperbarui supaya halaman lain tetap konsisten,
dan sel yang dikoreksi diakumulasi supaya bisa diunduh dengan penandaan warna.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st

from app.core.igt_config import get_igt_style, load_igt_list, slugify
from app.core.rules_manager import build_ri_ruleset_lookup
from app.core.session_state import (
    SS_CHANGED_CELLS,
    SS_DATA_SOURCE,
    SS_LAST_VERIFICATION,
    SS_MERGED_DF,
    SS_SUMBER_FILES,
    SS_VALIDATION_RESULT,
    init_working_dataset_state,
    reset_working_dataset_state,
)
from app.core.validator import (
    apply_value_corrections,
    build_corrected_dataset_excel,
    display_value,
    get_context_rows_for_value,
    get_invalid_value_groups,
    get_present_identity_columns,
    list_data_files,
    load_and_merge_data_files,
    split_and_write_back,
    validate_merged_dataframe,
    verify_after_correction,
)

st.set_page_config(page_title="Koreksi Data - IGT P4T", page_icon="🛠️", layout="wide")

init_working_dataset_state(st)

st.title("Koreksi Data")
st.write(
    "Untuk tiap **nilai unik** yang terdeteksi salah, pilih kandidat pengganti dari "
    "dropdown atau ketik langsung nilai yang benar (input manual selalu diutamakan "
    "kalau diisi). Satu koreksi berlaku untuk SEMUA baris yang punya nilai tsb, di "
    "semua file sumbernya. Klik **Terapkan Koreksi** untuk menyimpan ke data."
)

if st.button("🔄 Reset / Mulai Ulang"):
    reset_working_dataset_state(st)
    st.rerun()

TIDAK_DIUBAH = "__tidak_diubah__"

if st.session_state[SS_MERGED_DF] is None:
    data_files = list_data_files()
    if not data_files:
        st.warning(
            "Belum ada dataset kerja aktif dan folder `data/` juga kosong. Unggah file "
            "di halaman **Validasi Data**, atau letakkan file di folder `data/`."
        )
        st.stop()

    merged_df = load_and_merge_data_files(data_files)
    lookup = build_ri_ruleset_lookup()
    st.session_state[SS_MERGED_DF] = merged_df
    st.session_state[SS_SUMBER_FILES] = sorted(merged_df["SUMBER_FILE"].unique().tolist())
    st.session_state[SS_VALIDATION_RESULT] = validate_merged_dataframe(merged_df, ri_lookup=lookup)
    st.session_state[SS_DATA_SOURCE] = "folder"

merged_df = st.session_state[SS_MERGED_DF]
sumber_files = st.session_state[SS_SUMBER_FILES]
sumber_label = "folder `data/`" if st.session_state[SS_DATA_SOURCE] == "folder" else "upload manual"
st.caption(f"Dataset kerja aktif ({sumber_label}): {len(sumber_files)} file, {len(merged_df)} record — {', '.join(sumber_files)}.")

lookup = build_ri_ruleset_lookup()
groups = get_invalid_value_groups(merged_df, ri_lookup=lookup)

if st.session_state[SS_LAST_VERIFICATION] is not None:
    verifikasi = st.session_state[SS_LAST_VERIFICATION]
    st.subheader("Hasil Verifikasi Setelah Koreksi Terakhir")
    for (nama_igt, column), sisa in sorted(verifikasi.items()):
        if sisa == 0:
            st.success(f"{nama_igt} / `{column}`: semua nilai sudah cocok dengan ruleset. ✔")
        else:
            st.warning(f"{nama_igt} / `{column}`: masih ada **{sisa}** nilai unik yang belum cocok.")
    st.divider()

if st.session_state[SS_CHANGED_CELLS]:
    dataset_label = sumber_files[0].rsplit(".", 1)[0] if len(sumber_files) == 1 else f"gabungan_{len(sumber_files)}_file"
    file_name = f"hasil_koreksi_{slugify(dataset_label)}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    st.download_button(
        label="⬇️ Download Hasil Koreksi (Excel, seluruh dataset)",
        data=build_corrected_dataset_excel(merged_df, st.session_state[SS_CHANGED_CELLS]),
        file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    st.caption(
        f"Berisi seluruh {len(merged_df)} record & semua kolom asli — sel yang dikoreksi sistem "
        "ditandai kuning (lihat sheet 'Keterangan' untuk detail warna)."
    )
    st.divider()

if not groups:
    st.success("Tidak ada nilai salah untuk kolom Rinci yang punya ruleset aktif di dataset ini.")
    st.stop()

identity_columns = get_present_identity_columns(merged_df)
igt_list = load_igt_list()

st.subheader(f"Nilai Salah yang Perlu Dikoreksi ({len(groups)})")
st.caption(
    "Kandidat dengan skor kemiripan tertinggi sudah otomatis terpilih di dropdown — "
    "tinggal cek sekilas lalu klik **Terapkan Koreksi**, atau ganti pilihan/isi manual "
    "untuk baris yang memang tidak cocok."
)

header_cols = [3, 1, 1, 3, 3]
current_group_key = None

for i, group in enumerate(groups):
    group_header_key = (group.nama_igt, group.column)
    if group_header_key != current_group_key:
        current_group_key = group_header_key
        icon, bg_color, text_color = get_igt_style(group.nama_igt, igt_list)
        st.markdown(
            f"""<div style="background-color:{bg_color}; padding:10px 16px;
            border-radius:8px; margin:18px 0 8px 0;">
            <span style="font-size:1.25em; font-weight:700; color:{text_color};">
            {icon} {group.nama_igt}</span><br>
            <span style="font-size:0.85em; color:{text_color}; opacity:0.85;">
            Kolom: {group.column}</span></div>""",
            unsafe_allow_html=True,
        )
        header = st.columns(header_cols)
        header[0].markdown("**Nilai Saat Ini**")
        header[1].markdown("**Frekuensi**")
        header[2].markdown("**Kategori**")
        header[3].markdown("**Pilih Kandidat**")
        header[4].markdown("**Atau Ketik Manual (prioritas)**")

    row = st.columns(header_cols)
    row[0].write(display_value(group.nilai_saat_ini))
    row[1].write(group.frekuensi)
    row[2].write(group.kategori)

    group_key = f"{group.column}_{i}"
    # Kandidat skor tertinggi (urutan pertama) di paling atas & jadi default (index=0);
    # "-- Tidak diubah --" tetap tersedia di paling bawah untuk dipilih sadar oleh user.
    # Kalau tidak ada kandidat sama sekali, satu-satunya opsi adalah "Tidak diubah".
    option_values = [*[c["nilai"] for c in group.kandidat], TIDAK_DIUBAH]
    option_display = {TIDAK_DIUBAH: "-- Tidak diubah --"}
    for c in group.kandidat:
        option_display[c["nilai"]] = f"{c['nilai']} ({c['skor_persen']}%)"

    row[3].selectbox(
        "Pilih kandidat",
        options=option_values,
        index=0,
        key=f"select_{group_key}",
        format_func=lambda v, option_display=option_display: option_display[v],
        label_visibility="collapsed",
    )
    row[4].text_input(
        "Manual", key=f"manual_{group_key}", label_visibility="collapsed",
        placeholder="Ketik nilai yang benar",
    )

    if identity_columns:
        with st.expander(f"Lihat {group.frekuensi} baris terdampak (NO_URUT / wilayah administrasi)"):
            context_df = get_context_rows_for_value(merged_df, group.column, group.nilai_saat_ini)
            st.dataframe(context_df, use_container_width=True, hide_index=True)

st.divider()

if st.button("Terapkan Koreksi", type="primary"):
    corrections: dict[tuple[str, str], str] = {}

    for i, group in enumerate(groups):
        group_key = f"{group.column}_{i}"
        manual_value = st.session_state.get(f"manual_{group_key}", "").strip()
        selection = st.session_state.get(f"select_{group_key}", TIDAK_DIUBAH)

        if manual_value:
            final_value = manual_value
        elif selection != TIDAK_DIUBAH:
            final_value = selection
        else:
            continue

        corrections[(group.column, group.nilai_saat_ini)] = final_value

    if not corrections:
        st.warning("Tidak ada koreksi yang dipilih. Pilih kandidat atau isi input manual terlebih dahulu.")
    else:
        corrected_df, changed_cells = apply_value_corrections(merged_df, corrections)
        saved = split_and_write_back(corrected_df)

        verifikasi = verify_after_correction(corrected_df, ri_lookup=lookup)

        st.session_state[SS_MERGED_DF] = corrected_df
        st.session_state[SS_VALIDATION_RESULT] = validate_merged_dataframe(corrected_df, ri_lookup=lookup)
        st.session_state[SS_LAST_VERIFICATION] = verifikasi
        st.session_state[SS_CHANGED_CELLS] = st.session_state[SS_CHANGED_CELLS] | changed_cells

        for group_key in list(st.session_state.keys()):
            if group_key.startswith("select_") or group_key.startswith("manual_"):
                del st.session_state[group_key]

        affected_records = sum(
            group.frekuensi for group in groups if (group.column, group.nilai_saat_ini) in corrections
        )
        st.success(
            f"{len(corrections)} nilai unik dikoreksi ({affected_records} record total), "
            f"disimpan ke: {', '.join(saved.keys())}."
        )
        st.rerun()
