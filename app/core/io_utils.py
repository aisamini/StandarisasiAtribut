"""Utilitas membaca data atribut IGT P4T dari DBF, SHP (.dbf terlampir), atau CSV,
serta validasi struktur kolom dasarnya terhadap daftar kolom yang diharapkan.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pandas as pd
import shapefile
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


DBF_FIELD_NAME_MAX_LEN = 10
DBF_CHAR_FIELD_MAX_LEN = 254


def _infer_dbf_field_specs(df: pd.DataFrame) -> list[tuple[str, str, int, int]]:
    """Tentukan spesifikasi field DBF (nama, tipe, size, decimal) dari dtype tiap kolom.

    Nama field dipangkas maks 10 karakter (batas format DBF) dan dibuat unik.
    """
    specs: list[tuple[str, str, int, int]] = []
    used_names: set[str] = set()

    for column in df.columns:
        base_name = str(column).strip().upper()[:DBF_FIELD_NAME_MAX_LEN] or "COL"
        name = base_name
        counter = 1
        while name in used_names:
            suffix = str(counter)
            name = f"{base_name[: DBF_FIELD_NAME_MAX_LEN - len(suffix)]}{suffix}"
            counter += 1
        used_names.add(name)

        series = df[column]
        if pd.api.types.is_bool_dtype(series.dtype):
            specs.append((name, "L", 1, 0))
        elif pd.api.types.is_integer_dtype(series.dtype):
            specs.append((name, "N", 18, 0))
        elif pd.api.types.is_float_dtype(series.dtype):
            specs.append((name, "N", 19, 4))
        else:
            lengths = series.dropna().astype(str).map(len)
            max_len = int(lengths.max()) if not lengths.empty else 1
            size = max(1, min(max_len, DBF_CHAR_FIELD_MAX_LEN))
            specs.append((name, "C", size, 0))

    return specs


def write_dbf(path: str | Path, df: pd.DataFrame) -> Path:
    """Tulis DataFrame ke file .dbf, tipe field disimpulkan otomatis dari dtype kolom.

    Melempar DataWriteError jika penulisan gagal (mis. tabel kosong tanpa kolom).
    """
    path = Path(path)
    if df.empty and len(df.columns) == 0:
        raise DataWriteError("Tidak bisa menulis DBF: DataFrame tidak memiliki kolom.")

    specs = _infer_dbf_field_specs(df)

    try:
        with shapefile.Writer(dbf=str(path)) as writer:
            for name, ftype, size, decimal in specs:
                writer.field(name, ftype, size=size, decimal=decimal)

            for _, row in df.iterrows():
                record = {}
                for column, (name, ftype, size, decimal) in zip(df.columns, specs):
                    value = row[column]
                    if pd.isna(value):
                        record[name] = None
                    elif ftype == "N":
                        record[name] = float(value) if decimal else int(value)
                    elif ftype == "L":
                        record[name] = bool(value)
                    else:
                        record[name] = str(value)[:size]
                # Pakai keyword args: pyshp mengubah nilai None jadi field kosong hanya
                # lewat jalur ini (bukan lewat argumen posisional).
                writer.record(**record)
    except Exception as exc:  # noqa: BLE001
        raise DataWriteError(f"Gagal menulis file DBF '{path.name}': {exc}") from exc

    return path


def write_attribute_table(path: str | Path, df: pd.DataFrame) -> Path:
    """Tulis DataFrame kembali ke file sesuai format aslinya (.csv, .dbf, atau .shp).

    Untuk .shp, hanya file .dbf pendamping yang ditulis ulang — geometri (.shp/.shx)
    tidak diubah karena koreksi hanya menyentuh nilai atribut, bukan geometri.
    """
    path = Path(path)
    suffix = path.suffix.lower()

    if suffix == ".csv":
        return write_csv(path, df)

    if suffix == ".dbf":
        return write_dbf(path, df)

    if suffix == ".shp":
        return write_dbf(path.with_suffix(".dbf"), df)

    raise DataWriteError(
        f"Menyimpan langsung ke format '{suffix}' belum didukung. "
        f"Format yang didukung: .csv, .dbf, .shp (menulis .dbf pendamping)."
    )


def export_attribute_table_bytes(df: pd.DataFrame, suffix: str) -> bytes:
    """Tulis DataFrame ke file sementara (.csv atau .dbf) lalu kembalikan isinya sebagai bytes.

    Dipakai untuk membuat konten tombol download Streamlit (mis. hasil koreksi)
    tanpa perlu menyimpan file permanen di disk. Untuk data yang berasal dari
    shapefile (.shp), export sebagai .dbf karena geometri (.shp/.shx) tidak
    diubah oleh proses koreksi atribut.
    """
    suffix = suffix.lower()
    if not suffix.startswith("."):
        suffix = f".{suffix}"
    if suffix == ".shp":
        suffix = ".dbf"
    if suffix not in (".csv", ".dbf"):
        raise DataWriteError(f"Format export '{suffix}' tidak didukung untuk unduhan langsung.")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / f"export{suffix}"
        write_attribute_table(tmp_path, df)
        return tmp_path.read_bytes()
