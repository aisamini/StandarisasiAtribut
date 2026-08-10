"""Path konfigurasi terpusat untuk aplikasi validasi IGT P4T."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
RULES_DIR = BASE_DIR / "rules"
RULES_ACTIVE_DIR = RULES_DIR / "active"
RULES_ARCHIVE_DIR = RULES_DIR / "archive"
RULES_PRESETS_DIR = RULES_DIR / "presets"
OUTPUT_DIR = BASE_DIR / "output"

RULES_METADATA_PATH = RULES_ACTIVE_DIR / "_metadata.json"
IGT_CONFIG_PATH = RULES_DIR / "igt_config.json"

for _dir in (DATA_DIR, RULES_ACTIVE_DIR, RULES_ARCHIVE_DIR, RULES_PRESETS_DIR, OUTPUT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)
