"""Konfigurasi daftar IGT P4T (nama + prefix kolom) dan pola nama kolom bakunya.

Nama kolom ruleset TIDAK distandarisasi ke skema generik — harus persis memakai
nama asli sesuai Permen ATR No. 1 Tahun 2025, karena langsung dipakai pengolah data.
Setiap IGT punya prefix kolom sendiri, tapi pola sufiks level selalu sama:
KC=Kecil, MN=Menengah, BS=Besar, RI=Rinci. Tiap level punya 2 kolom: nama kategori
(mis. "pfnObjRI") dan kode (mis. "idpfnObjRI", prefix "id" + nama kolom).

Daftar IGT disimpan di rules/igt_config.json sehingga bisa ditambah lewat UI
("+ Tambah IGT Baru") tanpa mengubah kode.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from app.config import IGT_CONFIG_PATH

LEVELS = ["KC", "MN", "BS", "RI"]
LEVEL_NAMES = {"KC": "Kecil", "MN": "Menengah", "BS": "Besar", "RI": "Rinci"}

DEFAULT_IGT_LIST = [
    {"nama_igt": "Penggunaan Tanah", "prefix": "ptn"},
    {"nama_igt": "Pemanfaatan Tanah", "prefix": "pfn"},
    {"nama_igt": "Pemilikan Tanah", "prefix": "pmn"},
    {"nama_igt": "Penguasaan Tanah", "prefix": "psn"},
]


class IgtConfigError(Exception):
    """Dilempar saat menambah IGT baru gagal (nama/prefix tidak valid atau sudah dipakai)."""


def slugify(name: str) -> str:
    """Ubah teks bebas jadi token aman-nama-file (huruf/angka/underscore)."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", str(name).strip()).strip("_")
    return slug or "TANPA_NAMA"


def load_igt_list() -> list[dict]:
    """Muat daftar {nama_igt, prefix}. Membuat file konfigurasi default bila belum ada."""
    if not IGT_CONFIG_PATH.exists():
        save_igt_list(DEFAULT_IGT_LIST)
        return [dict(item) for item in DEFAULT_IGT_LIST]
    data = json.loads(IGT_CONFIG_PATH.read_text(encoding="utf-8"))
    return data.get("igt_list", [])


def save_igt_list(igt_list: list[dict]) -> None:
    IGT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    IGT_CONFIG_PATH.write_text(
        json.dumps({"igt_list": igt_list}, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def get_prefix(nama_igt: str, igt_list: list[dict] | None = None) -> str | None:
    """Cari prefix kolom untuk satu nama IGT, atau None kalau tidak terdaftar."""
    igt_list = igt_list if igt_list is not None else load_igt_list()
    for item in igt_list:
        if item["nama_igt"] == nama_igt:
            return item["prefix"]
    return None


def add_igt(nama_igt: str, prefix: str) -> list[dict]:
    """Tambah pasangan nama_igt+prefix baru ke konfigurasi. Mengembalikan daftar terbaru.

    Melempar IgtConfigError dengan pesan jelas kalau nama/prefix kosong, prefix
    tidak valid, atau nama_igt/prefix sudah dipakai IGT lain.
    """
    nama_igt = nama_igt.strip()
    prefix = prefix.strip()

    if not nama_igt:
        raise IgtConfigError("Nama IGT tidak boleh kosong.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", prefix):
        raise IgtConfigError(
            "Prefix kolom harus diawali huruf dan hanya boleh berisi huruf/angka "
            "tanpa spasi atau simbol (contoh: 'ptn')."
        )

    igt_list = load_igt_list()
    if any(item["nama_igt"].strip().lower() == nama_igt.lower() for item in igt_list):
        raise IgtConfigError(f"IGT dengan nama '{nama_igt}' sudah terdaftar.")
    if any(item["prefix"].lower() == prefix.lower() for item in igt_list):
        raise IgtConfigError(f"Prefix '{prefix}' sudah dipakai oleh IGT lain.")

    igt_list.append({"nama_igt": nama_igt, "prefix": prefix})
    save_igt_list(igt_list)
    return igt_list


def get_name_col(prefix: str, level: str) -> str:
    """Nama kolom kategori untuk prefix+level, mis. get_name_col('ptn','KC') -> 'ptnObjKC'."""
    return f"{prefix}Obj{level}"


def get_code_col(prefix: str, level: str) -> str:
    """Nama kolom kode untuk prefix+level, mis. get_code_col('ptn','KC') -> 'idptnObjKC'."""
    return f"id{prefix}Obj{level}"


def get_igt_columns(prefix: str) -> list[str]:
    """8 kolom baku (nama+kode x 4 level) untuk satu prefix IGT, urut KC, MN, BS, RI."""
    columns: list[str] = []
    for level in LEVELS:
        columns.append(get_name_col(prefix, level))
        columns.append(get_code_col(prefix, level))
    return columns


def detect_igt_ri_columns(
    columns: Iterable[str], igt_list: list[dict] | None = None
) -> list[dict]:
    """Deteksi kolom level Rinci ("[prefix]ObjRI") IGT mana saja yang ada di `columns`.

    Data spasial P4T di lapangan hanya punya kolom level Rinci per IGT (mis. "PTNOBJRI"),
    tanpa kolom terpisah untuk Besar/Menengah/Kecil, dan sering seluruhnya huruf besar —
    jadi perbandingan nama kolom dilakukan case-insensitive. Mengembalikan
    list of {"nama_igt", "prefix", "column"} (nama kolom asli sesuai `columns`).
    """
    igt_list = igt_list if igt_list is not None else load_igt_list()
    columns_by_upper: dict[str, str] = {str(c).upper(): c for c in columns}
    matches: list[dict] = []

    for item in igt_list:
        nama_igt, prefix = item["nama_igt"], item["prefix"]
        expected = get_name_col(prefix, "RI").upper()
        if expected in columns_by_upper:
            matches.append(
                {
                    "nama_igt": nama_igt,
                    "prefix": prefix,
                    "column": columns_by_upper[expected],
                }
            )

    return matches
