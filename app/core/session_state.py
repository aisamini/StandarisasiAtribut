"""Kunci st.session_state bersama & util init/reset, dipakai lintas halaman Streamlit.

Dipisah dari validator.py supaya app/core tetap bisa dites tanpa Streamlit terpasang;
modul ini hanya berisi nama key dan fungsi kecil yang menerima objek `st` sebagai
parameter (bukan mengimpor streamlit langsung).
"""

from __future__ import annotations

SS_MERGED_DF = "app_merged_df"
SS_SUMBER_FILES = "app_sumber_files"
SS_VALIDATION_RESULT = "app_validation_result"
SS_LAST_VERIFICATION = "app_last_verification"
SS_DATA_SOURCE = "app_data_source"

WORKING_DATASET_KEYS = [
    SS_MERGED_DF,
    SS_SUMBER_FILES,
    SS_VALIDATION_RESULT,
    SS_LAST_VERIFICATION,
    SS_DATA_SOURCE,
]

_DEFAULTS = {
    SS_MERGED_DF: None,
    SS_SUMBER_FILES: [],
    SS_VALIDATION_RESULT: None,
    SS_LAST_VERIFICATION: None,
    SS_DATA_SOURCE: None,
}


def init_working_dataset_state(st) -> None:
    """Inisialisasi key session_state dataset kerja kalau belum ada (aman dipanggil berkali-kali)."""
    for key, default in _DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default


def reset_working_dataset_state(st) -> None:
    """Hapus semua state dataset kerja saat ini (dipakai tombol Reset/Mulai Ulang)."""
    for key in WORKING_DATASET_KEYS:
        st.session_state.pop(key, None)
