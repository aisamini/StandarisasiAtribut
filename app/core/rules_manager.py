"""Pengelolaan ruleset atribut IGT P4T: template, validasi, arsip, dan update per kategori."""

from __future__ import annotations

import io
import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from app.config import (
    RULES_ACTIVE_DIR,
    RULES_ARCHIVE_DIR,
    RULES_METADATA_PATH,
    TEMPLATE_COLUMNS,
)


class RulesValidationError(Exception):
    """Dilempar saat file aturan yang diupload tidak sesuai template."""


def _slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(name).strip()).strip("_")
    return slug or "TANPA_KATEGORI"


def build_empty_template() -> bytes:
    """Buat file Excel kosong berisi header sesuai template ruleset."""
    df = pd.DataFrame(columns=TEMPLATE_COLUMNS)
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Aturan")
    buffer.seek(0)
    return buffer.getvalue()


def validate_columns(df: pd.DataFrame) -> None:
    """Pastikan kolom file yang diupload persis sesuai template.

    Melempar RulesValidationError dengan pesan jelas jika tidak sesuai.
    """
    actual_columns = list(df.columns)

    missing = [c for c in TEMPLATE_COLUMNS if c not in actual_columns]
    extra = [c for c in actual_columns if c not in TEMPLATE_COLUMNS]

    if missing or extra:
        parts = []
        if missing:
            parts.append(f"kolom hilang: {', '.join(missing)}")
        if extra:
            parts.append(f"kolom tidak dikenal: {', '.join(extra)}")
        raise RulesValidationError(
            "File tidak sesuai template. Kolom yang diharapkan: "
            f"{', '.join(TEMPLATE_COLUMNS)}. Ditemukan {', '.join(parts)}. "
            "Silakan unduh ulang template dan sesuaikan file Anda."
        )

    if actual_columns[: len(TEMPLATE_COLUMNS)] != TEMPLATE_COLUMNS:
        raise RulesValidationError(
            "Urutan kolom tidak sesuai template. Urutan yang diharapkan: "
            f"{', '.join(TEMPLATE_COLUMNS)}."
        )

    if df.empty:
        raise RulesValidationError("File aturan kosong, tidak ada baris data untuk disimpan.")

    if df["Kategori_IGT"].isna().any() or (df["Kategori_IGT"].astype(str).str.strip() == "").any():
        raise RulesValidationError("Ada baris dengan Kategori_IGT kosong. Lengkapi terlebih dahulu.")

    if df["Nama_Atribut"].isna().any() or (df["Nama_Atribut"].astype(str).str.strip() == "").any():
        raise RulesValidationError("Ada baris dengan Nama_Atribut kosong. Lengkapi terlebih dahulu.")


def _load_metadata() -> dict:
    if RULES_METADATA_PATH.exists():
        return json.loads(RULES_METADATA_PATH.read_text(encoding="utf-8"))
    return {}


def _save_metadata(metadata: dict) -> None:
    RULES_METADATA_PATH.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def save_archive_copy(uploaded_bytes: bytes, original_filename: str) -> Path:
    """Simpan salinan arsip file yang diupload dengan nama bertimestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = Path(original_filename).suffix or ".xlsx"
    stem = Path(original_filename).stem
    archive_name = f"{timestamp}_{_slugify(stem)}{suffix}"
    archive_path = RULES_ARCHIVE_DIR / archive_name
    archive_path.write_bytes(uploaded_bytes)
    return archive_path


def update_active_rules(df: pd.DataFrame) -> list[str]:
    """Update rules/active/ hanya untuk kategori yang ada di df.

    Kategori lain yang sudah ada di rules/active tidak disentuh.
    Mengembalikan daftar kategori yang diperbarui.
    """
    metadata = _load_metadata()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    updated_categories: list[str] = []
    for category, group in df.groupby("Kategori_IGT"):
        category = str(category).strip()
        category_df = group[TEMPLATE_COLUMNS].reset_index(drop=True)

        active_path = RULES_ACTIVE_DIR / f"{_slugify(category)}.csv"
        category_df.to_csv(active_path, index=False, encoding="utf-8")

        metadata[category] = {
            "file": active_path.name,
            "last_updated": now_str,
            "jumlah_atribut": len(category_df),
        }
        updated_categories.append(category)

    _save_metadata(metadata)
    return updated_categories


def get_active_rules_summary() -> pd.DataFrame:
    """Tabel ringkasan aturan aktif per kategori beserta tanggal update terakhir."""
    metadata = _load_metadata()
    rows = []
    for category, info in metadata.items():
        rows.append(
            {
                "Kategori_IGT": category,
                "Jumlah_Atribut": info.get("jumlah_atribut", 0),
                "Terakhir_Diupdate": info.get("last_updated", "-"),
                "File": info.get("file", "-"),
            }
        )
    if not rows:
        return pd.DataFrame(columns=["Kategori_IGT", "Jumlah_Atribut", "Terakhir_Diupdate", "File"])
    return pd.DataFrame(rows).sort_values("Kategori_IGT").reset_index(drop=True)


def load_active_rules_for_category(category: str) -> pd.DataFrame:
    """Muat ruleset aktif untuk satu kategori tertentu."""
    metadata = _load_metadata()
    info = metadata.get(category)
    if not info:
        return pd.DataFrame(columns=TEMPLATE_COLUMNS)
    path = RULES_ACTIVE_DIR / info["file"]
    if not path.exists():
        return pd.DataFrame(columns=TEMPLATE_COLUMNS)
    return pd.read_csv(path)


def get_expected_attributes(category: str) -> list[str]:
    """Daftar nama atribut yang diharapkan (kolom wajib) untuk satu kategori IGT."""
    rules_df = load_active_rules_for_category(category)
    if rules_df.empty:
        return []
    return sorted(rules_df["Nama_Atribut"].dropna().astype(str).str.strip().unique().tolist())


def get_active_categories() -> list[str]:
    """Daftar kategori IGT yang memiliki ruleset aktif."""
    return sorted(_load_metadata().keys())


def load_all_active_rules() -> pd.DataFrame:
    """Muat seluruh ruleset aktif dari semua kategori menjadi satu DataFrame."""
    metadata = _load_metadata()
    frames = []
    for category, info in metadata.items():
        path = RULES_ACTIVE_DIR / info["file"]
        if path.exists():
            frames.append(pd.read_csv(path))
    if not frames:
        return pd.DataFrame(columns=TEMPLATE_COLUMNS)
    return pd.concat(frames, ignore_index=True)
