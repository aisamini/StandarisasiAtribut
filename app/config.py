"""Path konfigurasi terpusat untuk aplikasi validasi IGT P4T."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RULES_DIR = BASE_DIR / "rules"
RULES_ACTIVE_DIR = RULES_DIR / "active"
RULES_ARCHIVE_DIR = RULES_DIR / "archive"
OUTPUT_DIR = BASE_DIR / "output"

RULES_METADATA_PATH = RULES_ACTIVE_DIR / "_metadata.json"

TEMPLATE_COLUMNS = ["Kategori_IGT", "Nama_Atribut", "Nilai_Valid"]

for _dir in (DATA_DIR, RULES_ACTIVE_DIR, RULES_ARCHIVE_DIR, OUTPUT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
