"""Deteksi & validasi atribut data spasial IGT P4T terhadap ruleset aktif per IGT+level.

Kolom IGT+level yang ada di sebuah file data dideteksi otomatis dari nama kolomnya
(lihat app/core/igt_config.py). Untuk tiap kombinasi IGT+level yang terdeteksi,
pasangan (kode, nama) tiap baris dicocokkan ke ruleset aktif IGT itu PADA LEVEL YANG
SAMA. Kandidat kemiripan (rapidfuzz) juga dicari hanya di antara nilai valid level
dan IGT yang sama — tidak pernah dicampur antar level atau antar IGT.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
from rapidfuzz import fuzz, process

from app.config import DATA_DIR, OUTPUT_DIR
from app.core.igt_config import detect_igt_level_columns, load_igt_list
from app.core.io_utils import SUPPORTED_EXTENSIONS, DataReadError, read_attribute_table
from app.core.rules_manager import build_ruleset_lookup

EMPTY_VALUE_LABEL = "(kosong)"
SUGGESTION_LIMIT = 3
VALIDATION_SNAPSHOT_PATH = OUTPUT_DIR / "validasi_terakhir.json"


def _pair_key(kode: str, nama: str) -> str:
    return f"{kode}||{nama}"


def _split_pair_key(key: str) -> tuple[str, str]:
    kode, _, nama = key.partition("||")
    return kode, nama


@dataclass
class LevelValidationResult:
    """Hasil validasi satu kombinasi IGT+level pada satu file data."""

    nama_igt: str
    level: str
    name_col: str
    code_col: str
    total_records: int
    ruleset_tersedia: bool
    error_count: int = 0
    # key = "kode||nama" -> frekuensi
    invalid_pair_counts: dict[str, int] = field(default_factory=dict)
    # key = "kode||nama" -> [{"kode":..,"nama":..,"skor_persen":..}, ...] top-3 kandidat
    suggestions: dict[str, list[dict[str, float | str]]] = field(default_factory=dict)


@dataclass
class FileValidationResult:
    """Hasil validasi satu file data, bisa mencakup lebih dari satu IGT+level."""

    data_file: str
    total_records: int
    level_results: list[LevelValidationResult] = field(default_factory=list)
    unmatched: bool = False  # True kalau tidak ada kolom IGT manapun yang terdeteksi di file ini


@dataclass
class InvalidPairRecord:
    """Satu record (baris) yang pasangan kode+nama-nya salah, siap dikoreksi."""

    row_index: int
    nama_igt: str
    level: str
    name_col: str
    code_col: str
    current_kode: str
    current_nama: str
    candidates: list[dict[str, float | str]] = field(default_factory=list)


def get_top_pair_suggestions(
    current_nama: str,
    valid_pairs: set[tuple[str, str]],
    limit: int = SUGGESTION_LIMIT,
) -> list[dict[str, float | str]]:
    """Cari top-N pasangan (kode, nama) valid paling mirip, dibandingkan lewat teks nama.

    Kandidat HANYA diambil dari valid_pairs yang diberikan (yaitu level+IGT yang sama
    dengan record yang sedang dikoreksi) — tidak pernah mencampur level/IGT lain.
    """
    if not valid_pairs or not current_nama or current_nama == EMPTY_VALUE_LABEL:
        return []

    nama_to_kode: dict[str, str] = {}
    for kode, nama in valid_pairs:
        nama_to_kode.setdefault(nama, kode)

    matches = process.extract(
        current_nama, list(nama_to_kode.keys()), scorer=fuzz.WRatio, limit=limit
    )
    return [
        {"kode": nama_to_kode[nama], "nama": nama, "skor_persen": round(float(score), 1)}
        for nama, score, _ in matches
    ]


def _pairs_and_invalid_mask(df: pd.DataFrame, name_col: str, code_col: str, valid_pairs: set[tuple[str, str]]):
    """Pasangan (kode, nama) per baris sebagai string, dan mask baris yang invalid."""
    nama_series = df[name_col].apply(lambda v: EMPTY_VALUE_LABEL if pd.isna(v) else str(v).strip())
    kode_series = df[code_col].apply(lambda v: EMPTY_VALUE_LABEL if pd.isna(v) else str(v).strip())
    pairs = list(zip(kode_series, nama_series))
    is_invalid = pd.Series([p not in valid_pairs for p in pairs], index=df.index)
    return kode_series, nama_series, is_invalid


def validate_dataframe_against_igt_rules(
    df: pd.DataFrame,
    igt_list: list[dict] | None = None,
    lookup: dict[str, dict[str, set[tuple[str, str]]]] | None = None,
    data_file: str = "",
) -> FileValidationResult:
    """Deteksi kombinasi IGT+level di df, lalu validasi tiap pasangan kode+nama per baris.

    Untuk level yang IGT-nya belum punya ruleset aktif, seluruh baris ditandai belum
    tervalidasi (ruleset_tersedia=False) supaya terlihat jelas perlu upload ruleset dulu.
    """
    if igt_list is None:
        igt_list = load_igt_list()
    if lookup is None:
        lookup = build_ruleset_lookup(igt_list)

    matches = detect_igt_level_columns(df.columns, igt_list)
    level_results: list[LevelValidationResult] = []

    for match in matches:
        nama_igt, level = match["nama_igt"], match["level"]
        name_col, code_col = match["name_col"], match["code_col"]

        valid_pairs = lookup.get(nama_igt, {}).get(level)
        ruleset_tersedia = valid_pairs is not None
        valid_pairs = valid_pairs or set()

        kode_series, nama_series, is_invalid = _pairs_and_invalid_mask(
            df, name_col, code_col, valid_pairs
        )
        if not ruleset_tersedia:
            is_invalid = pd.Series([True] * len(df), index=df.index)

        error_count = int(is_invalid.sum())
        invalid_pair_counts: dict[str, int] = {}
        for kode, nama, invalid in zip(kode_series, nama_series, is_invalid):
            if invalid:
                key = _pair_key(kode, nama)
                invalid_pair_counts[key] = invalid_pair_counts.get(key, 0) + 1

        suggestions: dict[str, list[dict[str, float | str]]] = {}
        if ruleset_tersedia:
            for key in invalid_pair_counts:
                _, nama = _split_pair_key(key)
                suggestions[key] = get_top_pair_suggestions(nama, valid_pairs)

        level_results.append(
            LevelValidationResult(
                nama_igt=nama_igt,
                level=level,
                name_col=name_col,
                code_col=code_col,
                total_records=len(df),
                ruleset_tersedia=ruleset_tersedia,
                error_count=error_count,
                invalid_pair_counts=invalid_pair_counts,
                suggestions=suggestions,
            )
        )

    return FileValidationResult(
        data_file=data_file,
        total_records=len(df),
        level_results=level_results,
        unmatched=not matches,
    )


def get_invalid_pair_records(
    df: pd.DataFrame,
    igt_list: list[dict] | None = None,
    lookup: dict[str, dict[str, set[tuple[str, str]]]] | None = None,
) -> list[InvalidPairRecord]:
    """Daftar record (baris) yang pasangan kode+nama-nya salah, siap ditampilkan di UI koreksi.

    Hanya mencakup kombinasi IGT+level yang SUDAH punya ruleset aktif (tanpa ruleset,
    tidak ada dasar untuk menyarankan koreksi).
    """
    if igt_list is None:
        igt_list = load_igt_list()
    if lookup is None:
        lookup = build_ruleset_lookup(igt_list)

    matches = detect_igt_level_columns(df.columns, igt_list)
    records: list[InvalidPairRecord] = []

    for match in matches:
        nama_igt, level = match["nama_igt"], match["level"]
        name_col, code_col = match["name_col"], match["code_col"]

        valid_pairs = lookup.get(nama_igt, {}).get(level)
        if valid_pairs is None:
            continue

        kode_series, nama_series, is_invalid = _pairs_and_invalid_mask(
            df, name_col, code_col, valid_pairs
        )
        for row_index in df.index[is_invalid]:
            current_kode = kode_series.loc[row_index]
            current_nama = nama_series.loc[row_index]
            records.append(
                InvalidPairRecord(
                    row_index=int(row_index),
                    nama_igt=nama_igt,
                    level=level,
                    name_col=name_col,
                    code_col=code_col,
                    current_kode=current_kode,
                    current_nama=current_nama,
                    candidates=get_top_pair_suggestions(current_nama, valid_pairs),
                )
            )

    return records


def list_data_files() -> list[Path]:
    """File data di data/ yang siap dibaca, tanpa duplikasi .shp+.dbf pasangan yang sama."""
    if not DATA_DIR.exists():
        return []
    paths = sorted(p for p in DATA_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    shp_stems = {p.stem for p in paths if p.suffix.lower() == ".shp"}
    return [p for p in paths if not (p.suffix.lower() == ".dbf" and p.stem in shp_stems)]


def run_validation_for_all_data_files() -> list[FileValidationResult]:
    """Jalankan validasi untuk semua file di data/, deteksi IGT+level otomatis per file."""
    igt_list = load_igt_list()
    lookup = build_ruleset_lookup(igt_list)

    results: list[FileValidationResult] = []
    for path in list_data_files():
        try:
            df = read_attribute_table(path)
        except DataReadError:
            continue
        results.append(
            validate_dataframe_against_igt_rules(df, igt_list, lookup, data_file=path.name)
        )
    return results


def save_validation_snapshot(results: list[FileValidationResult], path: Path | None = None) -> Path:
    """Simpan hasil validasi (termasuk saran koreksi rapidfuzz) ke output/ sebagai JSON.

    Snapshot ini dipakai oleh antarmuka koreksi supaya tidak perlu menjalankan
    ulang validasi hanya untuk menampilkan nilai salah dan kandidat penggantinya.
    """
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "results": [asdict(result) for result in results],
    }
    target_path = path or VALIDATION_SNAPSHOT_PATH
    target_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target_path


def load_validation_snapshot(path: Path | None = None) -> dict | None:
    """Muat snapshot hasil validasi terakhir yang tersimpan, atau None jika belum ada."""
    target_path = path or VALIDATION_SNAPSHOT_PATH
    if not target_path.exists():
        return None
    return json.loads(target_path.read_text(encoding="utf-8"))


def build_discrepancy_report_excel(results: list[FileValidationResult]) -> bytes:
    """Susun laporan ringkasan statistik diskrepansi hasil validasi jadi file Excel.

    Berisi 2 sheet:
      - Ringkasan: total record, jumlah salah, dan status ruleset per file+IGT+level.
      - Nilai_Tidak_Valid: tiap pasangan kode+nama salah, frekuensinya, dan top-3 kandidat.
    """
    ringkasan_rows = []
    invalid_rows = []

    for result in results:
        for lr in result.level_results:
            ringkasan_rows.append(
                {
                    "File_Data": result.data_file,
                    "Nama_IGT": lr.nama_igt,
                    "Level": lr.level,
                    "Ruleset_Tersedia": "Ya" if lr.ruleset_tersedia else "Tidak",
                    "Total_Record": lr.total_records,
                    "Jumlah_Record_Salah": lr.error_count,
                    "Persentase_Salah": (
                        round(lr.error_count / lr.total_records * 100, 2) if lr.total_records else 0.0
                    ),
                }
            )
            for key, freq in sorted(lr.invalid_pair_counts.items(), key=lambda kv: kv[1], reverse=True):
                kode, nama = _split_pair_key(key)
                candidates = lr.suggestions.get(key, [])
                candidates_str = (
                    "; ".join(f"{c['kode']} - {c['nama']} ({c['skor_persen']}%)" for c in candidates)
                    if candidates
                    else "-"
                )
                invalid_rows.append(
                    {
                        "File_Data": result.data_file,
                        "Nama_IGT": lr.nama_igt,
                        "Level": lr.level,
                        "Kode_Salah": kode,
                        "Nama_Salah": nama,
                        "Frekuensi": freq,
                        "Top3_Kandidat_Pengganti": candidates_str,
                    }
                )

    ringkasan_df = pd.DataFrame(
        ringkasan_rows,
        columns=[
            "File_Data",
            "Nama_IGT",
            "Level",
            "Ruleset_Tersedia",
            "Total_Record",
            "Jumlah_Record_Salah",
            "Persentase_Salah",
        ],
    )
    invalid_df = pd.DataFrame(
        invalid_rows,
        columns=[
            "File_Data",
            "Nama_IGT",
            "Level",
            "Kode_Salah",
            "Nama_Salah",
            "Frekuensi",
            "Top3_Kandidat_Pengganti",
        ],
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        ringkasan_df.to_excel(writer, index=False, sheet_name="Ringkasan")
        invalid_df.to_excel(writer, index=False, sheet_name="Nilai_Tidak_Valid")
    buffer.seek(0)
    return buffer.getvalue()
