"""Pengelolaan ruleset atribut IGT P4T: template per IGT, validasi upload, arsip, dan ruleset aktif.

Satu file ruleset = satu IGT lengkap (4 level: KC/MN/BS/RI sekaligus), dengan nama
kolom persis sesuai Permen ATR No. 1 Tahun 2025 (lihat app/core/igt_config.py).
Upload baru untuk IGT yang sama MENGGANTI SELURUH ruleset IGT itu (bukan digabung).
"""

from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.config import RULES_ACTIVE_DIR, RULES_ARCHIVE_DIR, RULES_METADATA_PATH
from app.core.igt_config import (
    LEVELS,
    get_code_col,
    get_igt_columns,
    get_name_col,
    get_prefix,
    load_igt_list,
    slugify,
)

EXAMPLE_ROW_VALUES = {
    "KC": ("Contoh Kategori Kecil", "1"),
    "MN": ("Contoh Kategori Menengah", "1.1"),
    "BS": ("Contoh Kategori Besar", "1.1.1"),
    "RI": ("Contoh Kategori Rinci", "1.1.1.1"),
}


class RulesValidationError(Exception):
    """Dilempar saat file ruleset yang diupload tidak sesuai template IGT terkait."""


def build_template_for_igt(nama_igt: str) -> bytes:
    """Buat file Excel template untuk satu IGT: 8 kolom baku + 1 baris contoh.

    Melempar ValueError kalau nama_igt tidak terdaftar di konfigurasi.
    """
    prefix = get_prefix(nama_igt)
    if prefix is None:
        raise ValueError(f"IGT '{nama_igt}' tidak terdaftar di konfigurasi.")

    columns = get_igt_columns(prefix)
    example_row = {}
    for level in LEVELS:
        nama_contoh, kode_contoh = EXAMPLE_ROW_VALUES[level]
        example_row[get_name_col(prefix, level)] = nama_contoh
        example_row[get_code_col(prefix, level)] = kode_contoh

    df = pd.DataFrame([example_row], columns=columns)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Ruleset")
    buffer.seek(0)
    return buffer.getvalue()


def validate_ruleset_columns(df: pd.DataFrame, nama_igt: str) -> None:
    """Pastikan kolom file yang diupload persis sesuai 8 kolom baku IGT tsb (case-sensitive).

    Melempar RulesValidationError dengan pesan jelas jika tidak sesuai.
    """
    prefix = get_prefix(nama_igt)
    if prefix is None:
        raise RulesValidationError(f"IGT '{nama_igt}' tidak terdaftar di konfigurasi.")

    expected_columns = get_igt_columns(prefix)
    actual_columns = list(df.columns)

    missing = [c for c in expected_columns if c not in actual_columns]
    extra = [c for c in actual_columns if c not in expected_columns]

    if missing or extra:
        parts = []
        if missing:
            parts.append(f"kolom hilang: {', '.join(missing)}")
        if extra:
            parts.append(f"kolom tidak dikenal: {', '.join(extra)}")
        raise RulesValidationError(
            f"File tidak sesuai template IGT '{nama_igt}'. Kolom yang diharapkan (persis, "
            f"case-sensitive): {', '.join(expected_columns)}. Ditemukan {', '.join(parts)}. "
            "Silakan unduh ulang template dan sesuaikan file Anda."
        )

    if df.empty:
        raise RulesValidationError("File ruleset kosong, tidak ada baris data untuk disimpan.")


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


def _count_valid_rows(df: pd.DataFrame, prefix: str, level: str) -> int:
    """Jumlah baris yang punya pasangan nama+kode terisi (bukan kosong) untuk satu level."""
    name_col, code_col = get_name_col(prefix, level), get_code_col(prefix, level)
    nama = df[name_col].astype(str).str.strip()
    kode = df[code_col].astype(str).str.strip()
    filled = df[name_col].notna() & df[code_col].notna() & (nama != "") & (kode != "") & (nama != "nan") & (kode != "nan")
    return int(filled.sum())


def update_active_ruleset(nama_igt: str, df: pd.DataFrame) -> Path:
    """Timpa seluruh ruleset aktif untuk satu IGT dengan isi df (4 level sekaligus).

    Ruleset IGT lain di rules/active/ tidak disentuh.
    """
    prefix = get_prefix(nama_igt)
    if prefix is None:
        raise RulesValidationError(f"IGT '{nama_igt}' tidak terdaftar di konfigurasi.")

    active_path = RULES_ACTIVE_DIR / f"{slugify(nama_igt)}.csv"
    df.to_csv(active_path, index=False, encoding="utf-8")

    metadata = _load_metadata()
    metadata[nama_igt] = {
        "file": active_path.name,
        "prefix": prefix,
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "jumlah_baris": {level: _count_valid_rows(df, prefix, level) for level in LEVELS},
    }
    _save_metadata(metadata)
    return active_path


def load_active_ruleset(nama_igt: str) -> pd.DataFrame | None:
    """Muat ruleset aktif (wide, 8 kolom) untuk satu IGT, atau None kalau belum ada."""
    metadata = _load_metadata()
    info = metadata.get(nama_igt)
    if not info:
        return None
    path = RULES_ACTIVE_DIR / info["file"]
    if not path.exists():
        return None
    return pd.read_csv(path, dtype=str)


def get_valid_ri_values(nama_igt: str) -> set[str] | None:
    """Set nilai valid level Rinci (kolom "[prefix]ObjRI") untuk satu IGT.

    Kolom Besar/Menengah/Kecil di ruleset tetap tersimpan untuk referensi/dokumentasi,
    tapi TIDAK dipakai di sini — validasi data spasial hanya di level Rinci (data
    lapangan cuma punya kolom Rinci per IGT, tanpa kolom level lain). Mengembalikan
    None kalau IGT belum punya ruleset aktif.
    """
    df = load_active_ruleset(nama_igt)
    if df is None:
        return None
    prefix = get_prefix(nama_igt)
    name_col = get_name_col(prefix, "RI")
    if name_col not in df.columns:
        return set()
    values = df[name_col].dropna().astype(str).str.strip()
    return set(values[values != ""])


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
    """Tabel ringkasan ruleset per IGT: status, jumlah baris per level, terakhir diupdate."""
    igt_list = igt_list if igt_list is not None else load_igt_list()
    metadata = _load_metadata()

    rows = []
    for item in igt_list:
        nama_igt, prefix = item["nama_igt"], item["prefix"]
        info = metadata.get(nama_igt)
        jumlah = info.get("jumlah_baris", {}) if info else {}
        rows.append(
            {
                "Nama_IGT": nama_igt,
                "Prefix": prefix,
                "Status": "Ada" if info else "Belum Ada",
                "Baris_KC": jumlah.get("KC", 0),
                "Baris_MN": jumlah.get("MN", 0),
                "Baris_BS": jumlah.get("BS", 0),
                "Baris_RI": jumlah.get("RI", 0),
                "Terakhir_Diupdate": info.get("last_updated", "-") if info else "-",
            }
        )
    return pd.DataFrame(rows)
