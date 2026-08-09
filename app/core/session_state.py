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
SS_CHANGED_CELLS = "app_changed_cells"

WORKING_DATASET_KEYS = [
    SS_MERGED_DF,
    SS_SUMBER_FILES,
    SS_VALIDATION_RESULT,
    SS_LAST_VERIFICATION,
    SS_DATA_SOURCE,
    SS_CHANGED_CELLS,
]

# Factory functions (bukan nilai langsung) supaya tiap sesi Streamlit dapat objek
# mutable (list/set) sendiri-sendiri, tidak berbagi referensi antar sesi.
_DEFAULT_FACTORIES = {
    SS_MERGED_DF: lambda: None,
    SS_SUMBER_FILES: list,
    SS_VALIDATION_RESULT: lambda: None,
    SS_LAST_VERIFICATION: lambda: None,
    SS_DATA_SOURCE: lambda: None,
    SS_CHANGED_CELLS: set,
}


def init_working_dataset_state(st) -> None:
    """Inisialisasi key session_state dataset kerja kalau belum ada (aman dipanggil berkali-kali)."""
    for key, factory in _DEFAULT_FACTORIES.items():
        if key not in st.session_state:
            st.session_state[key] = factory()


def reset_working_dataset_state(st) -> None:
    """Hapus semua state dataset kerja saat ini (dipakai tombol Reset/Mulai Ulang)."""
    for key in WORKING_DATASET_KEYS:
        st.session_state.pop(key, None)
