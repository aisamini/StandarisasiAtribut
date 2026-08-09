"""Pencocokan nilai atribut data spasial IGT P4T terhadap ruleset aktif (rules/active/).

Ruleset digabungkan dari seluruh kategori di rules/active/, lalu setiap file data
di data/ dicocokkan ke kategori yang sesuai berdasarkan nama file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.config import DATA_DIR
from app.core.io_utils import SUPPORTED_EXTENSIONS, DataReadError, read_attribute_table
from app.core.rules_manager import _slugify, load_all_active_rules

EMPTY_VALUE_LABEL = "(kosong)"


@dataclass
class AttributeValidationResult:
    """Hasil validasi satu atribut dalam satu kategori."""

    total_checked: int
    error_count: int
    invalid_value_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class CategoryValidationResult:
    """Hasil validasi seluruh atribut untuk satu kategori IGT."""

    category: str
    total_records: int
    data_file: str
    attribute_results: dict[str, AttributeValidationResult] = field(default_factory=dict)
    attributes_not_in_data: list[str] = field(default_factory=list)


def build_rules_lookup() -> dict[str, dict[str, set[str]]]:
    """Baca seluruh ruleset aktif dari rules/active/ (gabungan semua kategori).

    Mengembalikan dict {Kategori_IGT: {Nama_Atribut: {nilai_valid, ...}}}.
    Sel Nilai_Valid boleh berisi beberapa nilai dipisah titik koma (;).
    """
    all_rules = load_all_active_rules()
    lookup: dict[str, dict[str, set[str]]] = {}
    if all_rules.empty:
        return lookup

    for (category, attribute), group in all_rules.groupby(["Kategori_IGT", "Nama_Atribut"]):
        valid_values: set[str] = set()
        for raw in group["Nilai_Valid"].dropna().astype(str):
            for v in raw.split(";"):
                v = v.strip()
                if v:
                    valid_values.add(v)
        category = str(category).strip()
        attribute = str(attribute).strip()
        lookup.setdefault(category, {})[attribute] = valid_values

    return lookup


def validate_dataframe_against_rules(
    df: pd.DataFrame,
    category: str,
    lookup: dict[str, dict[str, set[str]]] | None = None,
    data_file: str = "",
) -> CategoryValidationResult:
    """Cocokkan setiap nilai atribut pada df terhadap daftar nilai valid kategori tsb.

    Untuk tiap atribut yang diatur ruleset dan ada di df: hitung jumlah record salah
    (nilai di luar daftar nilai valid, termasuk nilai kosong/NaN) dan frekuensi tiap
    unique invalid value. Atribut yang diatur ruleset tapi tidak ada kolomnya di df
    dicatat terpisah di attributes_not_in_data.
    """
    if lookup is None:
        lookup = build_rules_lookup()

    attribute_rules = lookup.get(category, {})
    attribute_results: dict[str, AttributeValidationResult] = {}
    attributes_not_in_data: list[str] = []

    for attribute, valid_values in attribute_rules.items():
        if attribute not in df.columns:
            attributes_not_in_data.append(attribute)
            continue

        values_as_str = df[attribute].apply(
            lambda v: EMPTY_VALUE_LABEL if pd.isna(v) else str(v).strip()
        )
        is_invalid = ~values_as_str.isin(valid_values)
        error_count = int(is_invalid.sum())
        invalid_value_counts = values_as_str[is_invalid].value_counts().to_dict()

        attribute_results[attribute] = AttributeValidationResult(
            total_checked=len(df),
            error_count=error_count,
            invalid_value_counts=invalid_value_counts,
        )

    return CategoryValidationResult(
        category=category,
        total_records=len(df),
        data_file=data_file,
        attribute_results=attribute_results,
        attributes_not_in_data=attributes_not_in_data,
    )


def _find_data_file_for_category(category: str) -> Path | None:
    """Cari file di data/ yang namanya cocok dengan kategori (dibandingkan sebagai slug)."""
    slug = _slugify(category)
    for path in sorted(DATA_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            if _slugify(path.stem) == slug:
                return path
    return None


def run_validation_for_all_categories() -> tuple[
    dict[str, CategoryValidationResult], list[str], list[str]
]:
    """Jalankan validasi nilai atribut untuk semua kategori.

    Mengembalikan tuple:
      - results: {kategori: CategoryValidationResult} untuk kategori yang punya
        ruleset aktif DAN file data yang cocok ditemukan di data/.
      - categories_missing_data: kategori dengan ruleset aktif tapi tidak ada file
        data yang cocok ditemukan di data/.
      - categories_missing_rules: nama kategori (dari nama file) yang ditemukan di
        data/ tapi belum punya ruleset aktif sama sekali.
    """
    lookup = build_rules_lookup()
    rule_categories = sorted(lookup.keys())
    rule_slugs = {_slugify(c) for c in rule_categories}

    results: dict[str, CategoryValidationResult] = {}
    categories_missing_data: list[str] = []

    for category in rule_categories:
        data_path = _find_data_file_for_category(category)
        if data_path is None:
            categories_missing_data.append(category)
            continue
        try:
            df = read_attribute_table(data_path)
        except DataReadError:
            categories_missing_data.append(category)
            continue
        results[category] = validate_dataframe_against_rules(
            df, category, lookup, data_file=data_path.name
        )

    categories_missing_rules: list[str] = []
    if DATA_DIR.exists():
        for path in sorted(DATA_DIR.iterdir()):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            if _slugify(path.stem) not in rule_slugs:
                categories_missing_rules.append(path.stem)

    return results, categories_missing_data, categories_missing_rules
