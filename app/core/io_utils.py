"""Utilitas membaca data atribut IGT P4T dari DBF, SHP (.dbf terlampir), atau CSV."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from dbfread import DBF


def read_dbf(path: str | Path) -> pd.DataFrame:
    """Baca tabel atribut dari file .dbf (termasuk .dbf pendamping shapefile)."""
    table = DBF(str(path), load=True, encoding="latin1")
    return pd.DataFrame(iter(table))


def read_csv(path: str | Path) -> pd.DataFrame:
    return pd.read_csv(path)


def read_attribute_table(path: str | Path) -> pd.DataFrame:
    """Baca tabel atribut otomatis berdasarkan ekstensi file (.dbf/.shp/.csv)."""
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".dbf":
        return read_dbf(path)
    if suffix == ".shp":
        return read_dbf(path.with_suffix(".dbf"))
    if suffix == ".csv":
        return read_csv(path)
    raise ValueError(f"Format file tidak didukung: {suffix}")
