"""Utilitas membaca data atribut IGT P4T dari DBF, SHP (.dbf terlampir), atau CSV,
serta validasi struktur kolom dasarnya terhadap daftar kolom yang diharapkan.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from dbfread import DBF, DBFNotFound


class DataReadError(Exception):
    """Dilempar saat file data spasial gagal dibaca (tidak ditemukan, rusak, atau format tak didukung)."""


class ColumnStructureError(Exception):
    """Dilempar saat struktur kolom tabel atribut tidak sesuai dengan yang diharapkan."""


class DataWriteError(Exception):
    """Dilempar saat hasil koreksi tidak bisa ditulis langsung ke format file aslinya."""


SUPPORTED_EXTENSIONS = (".dbf", ".shp", ".csv")


def read_dbf(path: str | Path) -> pd.DataFrame:
    """Baca tabel atribut dari file .dbf (termasuk .dbf pendamping shapefile).

    Melempar DataReadError dengan pesan jelas jika file tidak ada atau gagal dibaca.
    """
    path = Path(path)
    if not path.exists():
        raise DataReadError(f"File DBF tidak ditemukan: {path}")

    try:
        table = DBF(str(path), load=True, encoding="latin1")
        df = pd.DataFrame(iter(table))
    except DBFNotFound as exc:
        raise DataReadError(f"File DBF tidak ditemukan: {path}") from exc
    except Exception as exc:  # noqa: BLE001 - bungkus semua error baca jadi pesan jelas
        raise DataReadError(f"Gagal membaca file DBF '{path.name}': {exc}") from exc

    if df.empty and len(df.columns) == 0:
        raise DataReadError(f"File DBF '{path.name}' tidak memiliki kolom atribut.")

    return df


def read_csv(path: str | Path) -> pd.DataFrame:
    """Baca tabel atribut dari file .csv.

    Melempar DataReadError dengan pesan jelas jika file tidak ada atau gagal dibaca.
    """
    path = Path(path)
    if not path.exists():
        raise DataReadError(f"File CSV tidak ditemukan: {path}")

    try:
        return pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        raise DataReadError(f"Gagal membaca file CSV '{path.name}': {exc}") from exc


def read_attribute_table(path: str | Path) -> pd.DataFrame:
    """Baca tabel atribut otomatis berdasarkan ekstensi file (.dbf/.shp/.csv).

    Untuk .shp, tabel atribut diambil dari file .dbf pendamping dengan nama yang sama.
    Melempar DataReadError dengan pesan jelas jika format tidak didukung atau file
    pendamping tidak ditemukan.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise DataReadError(
            f"Format file '{suffix or path.name}' tidak didukung. "
            f"Format yang didukung: {', '.join(SUPPORTED_EXTENSIONS)}."
        )

    if suffix == ".dbf":
        return read_dbf(path)

    if suffix == ".shp":
        dbf_path = path.with_suffix(".dbf")
        if not dbf_path.exists():
            raise DataReadError(
                f"File .dbf pendamping tidak ditemukan untuk shapefile '{path.name}'. "
                f"Pastikan file '{dbf_path.name}' berada di folder yang sama."
            )
        return read_dbf(dbf_path)

    return read_csv(path)


def validate_column_structure(
    df: pd.DataFrame,
    expected_columns: list[str],
    source_name: str = "file",
) -> None:
    """Validasi struktur kolom dasar: pastikan semua kolom yang diharapkan ada di df.

    Kolom tambahan di luar yang diharapkan diperbolehkan (tidak dianggap error).
    Melempar ColumnStructureError dengan pesan jelas jika ada kolom yang hilang.
    """
    if not expected_columns:
        raise ValueError("expected_columns tidak boleh kosong.")

    actual_columns = list(df.columns)
    missing = [c for c in expected_columns if c not in actual_columns]

    if missing:
        raise ColumnStructureError(
            f"Struktur kolom pada '{source_name}' tidak sesuai. "
            f"Kolom yang wajib ada namun tidak ditemukan: {', '.join(missing)}. "
            f"Kolom yang ditemukan pada file: {', '.join(actual_columns) if actual_columns else '(tidak ada)'}."
        )


def load_and_validate_attribute_table(
    path: str | Path,
    expected_columns: list[str],
) -> pd.DataFrame:
    """Baca tabel atribut dari file lalu validasi struktur kolom dasarnya sekaligus.

    Menggabungkan read_attribute_table dan validate_column_structure sehingga
    pemanggil cukup menangani DataReadError dan ColumnStructureError.
    """
    path = Path(path)
    df = read_attribute_table(path)
    validate_column_structure(df, expected_columns, source_name=path.name)
    return df


def write_csv(path: str | Path, df: pd.DataFrame) -> Path:
    """Tulis DataFrame ke file .csv."""
    path = Path(path)
    df.to_csv(path, index=False)
    return path


def write_attribute_table(path: str | Path, df: pd.DataFrame) -> Path:
    """Tulis DataFrame kembali ke file sesuai format aslinya.

    Hanya .csv yang didukung untuk ditulis langsung. Untuk .dbf/.shp,
    melempar DataWriteError dengan pesan jelas — pemanggil disarankan
    menyimpan hasil koreksi sebagai file .csv baru sebagai gantinya.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return write_csv(path, df)

    raise DataWriteError(
        f"Menyimpan langsung ke format '{suffix}' belum didukung. "
        "Simpan hasil koreksi sebagai file .csv baru sebagai gantinya."
    )
