"""Konfigurasi daftar IGT P4T (nama + prefix kolom) dan pola nama kolom Rinci bakunya.

Data spasial P4T di lapangan hanya punya SATU kolom atribut relevan per IGT: level
Rinci, bernama "[PREFIX]OBJRI" — huruf besar semua, konsisten dengan nama kolom asli
di data spasial (mis. "PTNOBJRI" untuk Penggunaan Tanah, prefix "ptn"). Perbandingan
nama kolom selalu case-insensitive (terima "ptnObjRI", "PTNOBJRI", dst — semua
dianggap sama dan distandarisasi jadi huruf besar).

Daftar IGT disimpan di rules/igt_config.json sehingga bisa ditambah lewat UI
("+ Tambah IGT Baru") tanpa mengubah kode.
"""

from __future__ import annotations

import json
import re
from typing import Iterable

from app.config import IGT_CONFIG_PATH

RI_SUFFIX = "OBJRI"

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


def get_ri_column(prefix: str) -> str:
    """Nama kolom Rinci baku (huruf besar) untuk satu prefix, mis. get_ri_column('ptn') -> 'PTNOBJRI'."""
    return f"{prefix.upper()}{RI_SUFFIX}"


def detect_igt_ri_columns(
    columns: Iterable[str], igt_list: list[dict] | None = None
) -> list[dict]:
    """Deteksi kolom Rinci ("[PREFIX]OBJRI") IGT mana saja yang ada di `columns`.

    Perbandingan case-insensitive. Mengembalikan list of {"nama_igt", "prefix",
    "column" (nama baku huruf besar), "source_column" (nama asli persis di `columns`)}.
    """
    igt_list = igt_list if igt_list is not None else load_igt_list()
    columns_by_upper: dict[str, str] = {str(c).upper(): c for c in columns}
    matches: list[dict] = []

    for item in igt_list:
        nama_igt, prefix = item["nama_igt"], item["prefix"]
        expected = get_ri_column(prefix)
        if expected in columns_by_upper:
            matches.append(
                {
                    "nama_igt": nama_igt,
                    "prefix": prefix,
                    "column": expected,
                    "source_column": columns_by_upper[expected],
                }
            )

    return matches
