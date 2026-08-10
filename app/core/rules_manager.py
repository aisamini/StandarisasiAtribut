"""Pengelolaan ruleset atribut IGT P4T: template per IGT, validasi upload, arsip, dan ruleset aktif.

Ruleset per IGT hanya berisi SATU kolom yang relevan: nilai valid level Rinci
("[PREFIX]OBJRI", huruf besar — lihat app/core/igt_config.py). Saat upload, kolom
itu dicari case-insensitive; kolom lain di file yang diupload diabaikan saja (tidak
dianggap error). Upload baru untuk IGT yang sama MENGGANTI SELURUH ruleset IGT itu.
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.config import RULES_ACTIVE_DIR, RULES_ARCHIVE_DIR, RULES_METADATA_PATH, RULES_PRESETS_DIR
from app.core.igt_config import get_prefix, get_ri_column, load_igt_list, slugify

EXAMPLE_VALUES = ["Contoh Kategori Rinci 1", "Contoh Kategori Rinci 2"]


class RulesValidationError(Exception):
    """Dilempar saat kolom Rinci yang relevan tidak ditemukan di file ruleset yang diupload."""


def find_ri_column(df: pd.DataFrame, nama_igt: str) -> str | None:
    """Cari kolom Rinci IGT tsb di df, case-insensitive. Return nama kolom ASLI di df, atau None."""
    prefix = get_prefix(nama_igt)
    if prefix is None:
        return None
    expected = get_ri_column(prefix)
    for column in df.columns:
        if str(column).strip().upper() == expected:
            return column
    return None


def build_template_for_igt(nama_igt: str) -> bytes:
    """Buat file Excel template untuk satu IGT: 1 kolom Rinci baku + beberapa baris contoh.

    Melempar ValueError kalau nama_igt tidak terdaftar di konfigurasi.
    """
    prefix = get_prefix(nama_igt)
    if prefix is None:
        raise ValueError(f"IGT '{nama_igt}' tidak terdaftar di konfigurasi.")

    column = get_ri_column(prefix)
    df = pd.DataFrame({column: EXAMPLE_VALUES})
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ruleset")
    buffer.seek(0)
    return buffer.getvalue()


def validate_ruleset_columns(df: pd.DataFrame, nama_igt: str) -> str:
    """Pastikan kolom Rinci yang relevan untuk IGT tsb ada di df (case-insensitive).

    Kolom lain di df diabaikan (bukan error). Melempar RulesValidationError dengan
    pesan jelas (sebutkan nama kolom yang dicari) kalau kolom itu tidak ditemukan
    sama sekali, atau kalau file kosong. Mengembalikan nama kolom ASLI yang ditemukan.
    """
    prefix = get_prefix(nama_igt)
    if prefix is None:
        raise RulesValidationError(f"IGT '{nama_igt}' tidak terdaftar di konfigurasi.")

    expected = get_ri_column(prefix)
    found_column = find_ri_column(df, nama_igt)

    if found_column is None:
        found_list = ", ".join(str(c) for c in df.columns) if len(df.columns) else "(tidak ada)"
        raise RulesValidationError(
            f"Kolom '{expected}' tidak ditemukan di file yang diupload untuk IGT '{nama_igt}'. "
            f"Kolom yang ditemukan pada file: {found_list}. Pastikan file memiliki kolom ini "
            "(nama kolom tidak harus persis huruf besar/kecil)."
        )

    if df.empty:
        raise RulesValidationError("File ruleset kosong, tidak ada baris data untuk disimpan.")

    return found_column


def _load_metadata() -> dict:
    if RULES_METADATA_PATH.exists():
        return json.loads(RULES_METADATA_PATH.read_text(encoding="utf-8"))
    return {}


def _save_metadata(metadata: dict) -> None:
    RULES_METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def save_archive_copy(uploaded_bytes: bytes, nama_igt: str, original_filename: str) -> Path:
    """Simpan salinan arsip file yang diupload, nama file bertimestamp + nama IGT."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = Path(original_filename).suffix or ".xlsx"
    archive_name = f"{timestamp}_{slugify(nama_igt)}{suffix}"
    archive_path = RULES_ARCHIVE_DIR / archive_name
    archive_path.write_bytes(uploaded_bytes)
    return archive_path


def update_active_ruleset(nama_igt: str, df: pd.DataFrame, found_column: str | None = None) -> Path:
    """Timpa ruleset aktif untuk satu IGT dengan daftar nilai unik non-kosong dari kolom Rinci.

    `found_column` (nama kolom asli di df) bisa dioper langsung dari hasil
    validate_ruleset_columns() supaya tidak dicari ulang; kalau tidak dioper, dicari lagi.
    Ruleset IGT lain di rules/active/ tidak disentuh.
    """
    prefix = get_prefix(nama_igt)
    if prefix is None:
        raise RulesValidationError(f"IGT '{nama_igt}' tidak terdaftar di konfigurasi.")
    if found_column is None:
        found_column = validate_ruleset_columns(df, nama_igt)

    standard_column = get_ri_column(prefix)
    raw_values = df[found_column].dropna().astype(str).str.strip()
    valid_values = sorted({v for v in raw_values if v})

    active_path = RULES_ACTIVE_DIR / f"{slugify(nama_igt)}.csv"
    pd.DataFrame({standard_column: valid_values}).to_csv(active_path, index=False, encoding="utf-8")

    metadata = _load_metadata()
    metadata[nama_igt] = {
        "file": active_path.name,
        "prefix": prefix,
        "column": standard_column,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "jumlah_nilai": len(valid_values),
    }
    _save_metadata(metadata)
    return active_path


def get_preset_dir(nama_igt: str) -> Path:
    """Folder preset klasifikasi resmi bawaan untuk satu IGT: rules/presets/<slug_igt>/."""
    return RULES_PRESETS_DIR / slugify(nama_igt)


def list_presets(nama_igt: str) -> list[dict]:
    """Daftar preset klasifikasi resmi bawaan yang tersedia untuk satu IGT.

    Dibaca dari file .xlsx di rules/presets/<slug_igt>/ — bukan hardcode di Python,
    supaya preset bisa ditambah/diganti cukup dengan menaruh file baru di folder itu.
    Mengembalikan list kosong (bukan error) kalau foldernya belum ada/masih kosong.
    Tiap entri: {"filename": nama file asli, "label": label untuk ditampilkan di
    dropdown (nama file tanpa ekstensi, underscore jadi spasi), "path": Path lengkap}.
    """
    preset_dir = get_preset_dir(nama_igt)
    if not preset_dir.exists():
        return []

    return [
        {"filename": path.name, "label": path.stem.replace("_", " "), "path": path}
        for path in sorted(preset_dir.glob("*.xlsx"))
    ]


def get_preset_preview(nama_igt: str, filename: str) -> dict:
    """Baca sekilas 1 file preset: kolom yang ditemukan, jumlah baris, jumlah nilai valid unik.

    Dipakai supaya user bisa lihat isinya sebelum diterapkan (bukan kotak hitam).
    Melempar RulesValidationError (pesan sama seperti validasi upload) kalau kolom
    Rinci yang relevan tidak ditemukan di file preset ini.
    """
    path = get_preset_dir(nama_igt) / filename
    df = pd.read_excel(path, dtype=str)
    found_column = validate_ruleset_columns(df, nama_igt)
    raw_values = df[found_column].dropna().astype(str).str.strip()
    jumlah_nilai_valid = len({v for v in raw_values if v})
    return {"kolom": found_column, "jumlah_baris": len(df), "jumlah_nilai_valid": jumlah_nilai_valid}


def apply_preset(nama_igt: str, filename: str) -> tuple[Path, Path]:
    """Terapkan preset klasifikasi resmi jadi ruleset aktif untuk satu IGT.

    Mengikuti alur yang sama persis dengan upload manual: file preset diarsipkan
    bertimestamp lewat save_archive_copy(), lalu jadi ruleset aktif lewat
    update_active_ruleset() — logika arsip & penyimpanan ruleset aktif TIDAK
    diduplikasi, cuma sumber filenya beda (baca dari rules/presets/ bukan dari
    upload). Ruleset IGT lain tidak disentuh. Mengembalikan (archive_path, active_path).
    """
    preset_dir = get_preset_dir(nama_igt)
    path = preset_dir / filename
    if not path.exists():
        raise RulesValidationError(f"Preset '{filename}' tidak ditemukan untuk IGT '{nama_igt}'.")

    preset_bytes = path.read_bytes()
    df = pd.read_excel(path, dtype=str)
    found_column = validate_ruleset_columns(df, nama_igt)

    archive_path = save_archive_copy(preset_bytes, nama_igt, filename)
    active_path = update_active_ruleset(nama_igt, df, found_column)
    return archive_path, active_path


def get_valid_ri_values(nama_igt: str) -> set[str] | None:
    """Set nilai valid level Rinci untuk satu IGT, atau None kalau belum punya ruleset aktif."""
    metadata = _load_metadata()
    info = metadata.get(nama_igt)
    if not info:
        return None

    path = RULES_ACTIVE_DIR / info["file"]
    if not path.exists():
        return set()

    df = pd.read_csv(path, dtype=str)
    column = info.get("column") or get_ri_column(info.get("prefix", ""))
    if column not in df.columns:
        return set()

    values = df[column].dropna().astype(str).str.strip()
    return set(v for v in values if v)


def build_ri_ruleset_lookup(igt_list: list[dict] | None = None) -> dict[str, set[str]]:
    """{nama_igt: {nilai_valid_rinci, ...}} — hanya untuk IGT yang sudah punya ruleset aktif."""
    igt_list = igt_list if igt_list is not None else load_igt_list()
    lookup: dict[str, set[str]] = {}
    for item in igt_list:
        nama_igt = item["nama_igt"]
        valid_values = get_valid_ri_values(nama_igt)
        if valid_values is not None:
            lookup[nama_igt] = valid_values
    return lookup


def get_ruleset_summary(igt_list: list[dict] | None = None) -> pd.DataFrame:
    """Tabel ringkasan ruleset per IGT: kolom, status, jumlah nilai valid, terakhir diupdate."""
    igt_list = igt_list if igt_list is not None else load_igt_list()
    metadata = _load_metadata()

    rows = []
    for item in igt_list:
        nama_igt, prefix = item["nama_igt"], item["prefix"]
        info = metadata.get(nama_igt)
        rows.append(
            {
                "Nama_IGT": nama_igt,
                "Kolom": get_ri_column(prefix),
                "Status": "Ada" if info else "Belum Ada",
                "Jumlah_Nilai_Valid": info.get("jumlah_nilai", 0) if info else 0,
                "Terakhir_Diupdate": info.get("last_updated", "-") if info else "-",
            }
        )
    return pd.DataFrame(rows)
