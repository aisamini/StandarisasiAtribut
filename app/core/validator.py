"""Validasi atribut data spasial IGT P4T level Rinci terhadap ruleset aktif.

Data spasial P4T di lapangan hanya punya kolom level Rinci per IGT (mis. PTNOBJRI),
jadi validasi HANYA mencocokkan kolom itu ke daftar nilai valid Rinci
("[PREFIX]OBJRI", huruf besar) di ruleset IGT terkait. Nama kolom dicocokkan
case-insensitive lalu distandarisasi ke huruf besar secara internal.

Banyak file data spasial bisa digabung jadi satu dataset (dengan kolom SUMBER_FILE
untuk pelacakan asal baris) sebelum divalidasi. Fuzzy matching (rapidfuzz) dihitung
sekali per NILAI UNIK yang salah per kolom, lalu hasilnya dipakai untuk semua baris
yang punya nilai itu — bukan dihitung ulang per baris.
"""

from __future__ import annotations

import io
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd
from openpyxl.styles import Font, PatternFill
from rapidfuzz import fuzz, process

from app.config import DATA_DIR, OUTPUT_DIR
from app.core.igt_config import detect_igt_ri_columns, load_igt_list
from app.core.io_utils import (
    SUPPORTED_EXTENSIONS,
    DataReadError,
    read_attribute_table,
    write_attribute_table,
)
from app.core.rules_manager import build_ri_ruleset_lookup

SUGGESTION_LIMIT = 5
VALIDATION_SNAPSHOT_PATH = OUTPUT_DIR / "validasi_terakhir.json"

SUMBER_FILE_COL = "SUMBER_FILE"
ROW_ASAL_COL = "_ROW_ASAL"

DUMMY_VALUES = {"", "-", ".", "0", "NAN"}
ERROR_KEYWORDS = ["KOSONG", "UNKNOWN", "SALAH", "ERROR", "TIDAK ADA", "XXX"]
MIN_VALID_LENGTH = 3

KATEGORI_SALAH_TOTAL = "Salah Total"
KATEGORI_TYPO = "Typo"


def display_value(value: str) -> str:
    """Representasi tampilan untuk nilai kosong (string kosong -> '(kosong)')."""
    return "(kosong)" if value == "" else value


def classify_error(value) -> str:
    """Klasifikasikan satu nilai salah: 'Salah Total' atau 'Typo'.

    Salah Total: kosong/null, nilai dummy ("-", ".", "0"), mengandung kata kunci error
    (KOSONG/UNKNOWN/SALAH/ERROR/TIDAK ADA/XXX), atau panjang teks < 3 karakter.
    Selain itu dianggap Typo (kemungkinan cuma salah ketik minor).
    """
    if pd.isna(value):
        return KATEGORI_SALAH_TOTAL

    text = str(value).strip()
    text_upper = text.upper()

    if text_upper in DUMMY_VALUES:
        return KATEGORI_SALAH_TOTAL
    if any(keyword in text_upper for keyword in ERROR_KEYWORDS):
        return KATEGORI_SALAH_TOTAL
    if len(text) < MIN_VALID_LENGTH:
        return KATEGORI_SALAH_TOTAL
    return KATEGORI_TYPO


def list_data_files() -> list[Path]:
    """File data di data/ yang siap dibaca, tanpa duplikasi .shp+.dbf pasangan yang sama."""
    if not DATA_DIR.exists():
        return []
    paths = sorted(p for p in DATA_DIR.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
    shp_stems = {p.stem for p in paths if p.suffix.lower() == ".shp"}
    return [p for p in paths if not (p.suffix.lower() == ".dbf" and p.stem in shp_stems)]


def _standardize_ri_column_names(df: pd.DataFrame, igt_list: list[dict] | None = None) -> pd.DataFrame:
    """Ganti nama kolom Rinci yang terdeteksi (case-insensitive) jadi bentuk baku huruf besar.

    Kolom lain (mis. NO_URUT, WADMKK) tidak disentuh. Memastikan file-file dengan
    variasi huruf besar/kecil pada kolom Rinci yang sama tetap tergabung jadi satu
    kolom saat digabung dengan pd.concat.
    """
    matches = detect_igt_ri_columns(df.columns, igt_list)
    rename_map = {m["source_column"]: m["column"] for m in matches if m["source_column"] != m["column"]}
    return df.rename(columns=rename_map) if rename_map else df


def load_and_merge_data_files(paths: list[Path], igt_list: list[dict] | None = None) -> pd.DataFrame:
    """Baca banyak file data (Excel/DBF/CSV) lalu gabungkan jadi satu DataFrame.

    Kolom Rinci di tiap file distandarisasi ke huruf besar (case-insensitive) supaya
    file dengan variasi penulisan kolom yang sama tetap tergabung jadi satu kolom.
    Menambahkan kolom SUMBER_FILE (nama file asal tiap baris, untuk pelacakan) dan
    _ROW_ASAL (index baris di file asalnya, dipakai untuk menulis koreksi balik ke
    file yang tepat). File yang gagal dibaca dilewati.
    """
    if igt_list is None:
        igt_list = load_igt_list()

    frames = []
    for path in paths:
        try:
            df = read_attribute_table(path)
        except DataReadError:
            continue
        df = _standardize_ri_column_names(df, igt_list).reset_index(drop=True)
        df.insert(0, ROW_ASAL_COL, df.index)
        df.insert(0, SUMBER_FILE_COL, path.name)
        frames.append(df)

    if not frames:
        return pd.DataFrame(columns=[SUMBER_FILE_COL, ROW_ASAL_COL])
    return pd.concat(frames, ignore_index=True, sort=False)


def build_unique_value_info(
    series: pd.Series, valid_values: set[str], limit: int = SUGGESTION_LIMIT
) -> dict[str, dict]:
    """Untuk tiap nilai unik pada `series` yang TIDAK ada di valid_values: klasifikasi
    kategori error + top-N kandidat kemiripan — dihitung SEKALI per nilai unik.

    Mengembalikan {nilai: {"frekuensi": int, "kategori": str, "kandidat": [...]}}.
    Kandidat hanya dihitung untuk kategori Typo (Salah Total tidak punya dasar teks
    yang cukup untuk disarankan otomatis, perlu koreksi manual).
    """
    text_series = series.apply(lambda v: "" if pd.isna(v) else str(v).strip())
    invalid_mask = ~text_series.isin(valid_values)
    counts = text_series[invalid_mask].value_counts()

    valid_list = list(valid_values)
    info: dict[str, dict] = {}
    for value, freq in counts.items():
        kategori = classify_error(value)
        candidates: list[dict[str, float | str]] = []
        if kategori == KATEGORI_TYPO and valid_list:
            matches = process.extract(value, valid_list, scorer=fuzz.WRatio, limit=limit)
            candidates = [
                {"nilai": candidate, "skor_persen": round(float(score), 1)}
                for candidate, score, _ in matches
            ]
        info[value] = {"frekuensi": int(freq), "kategori": kategori, "kandidat": candidates}

    return info


@dataclass
class ColumnValidationStats:
    """Statistik validasi satu kolom Rinci (satu IGT) pada dataset gabungan."""

    nama_igt: str
    column: str
    total_checked: int
    ruleset_tersedia: bool
    valid_count: int = 0
    salah_total_count: int = 0
    typo_count: int = 0
    # {nilai: {"frekuensi": int, "kategori": str, "kandidat": [...]}}
    unique_value_info: dict[str, dict] = field(default_factory=dict)


@dataclass
class MergedValidationResult:
    """Hasil validasi atas dataset gabungan (bisa berasal dari banyak file)."""

    total_records: int
    sumber_files: list[str] = field(default_factory=list)
    column_stats: list[ColumnValidationStats] = field(default_factory=list)


def validate_merged_dataframe(
    df: pd.DataFrame,
    igt_list: list[dict] | None = None,
    ri_lookup: dict[str, set[str]] | None = None,
) -> MergedValidationResult:
    """Deteksi kolom Rinci per IGT di df, lalu validasi & klasifikasikan tiap nilai."""
    if igt_list is None:
        igt_list = load_igt_list()
    if ri_lookup is None:
        ri_lookup = build_ri_ruleset_lookup(igt_list)

    matches = detect_igt_ri_columns(df.columns, igt_list)
    column_stats: list[ColumnValidationStats] = []

    for match in matches:
        nama_igt, column = match["nama_igt"], match["column"]
        valid_values = ri_lookup.get(nama_igt)
        ruleset_tersedia = valid_values is not None
        valid_values = valid_values or set()

        if ruleset_tersedia:
            unique_info = build_unique_value_info(df[column], valid_values)
            error_total = sum(v["frekuensi"] for v in unique_info.values())
            salah_total_count = sum(
                v["frekuensi"] for v in unique_info.values() if v["kategori"] == KATEGORI_SALAH_TOTAL
            )
            typo_count = error_total - salah_total_count
            valid_count = len(df) - error_total
        else:
            unique_info, salah_total_count, typo_count, valid_count = {}, 0, 0, 0

        column_stats.append(
            ColumnValidationStats(
                nama_igt=nama_igt,
                column=column,
                total_checked=len(df),
                ruleset_tersedia=ruleset_tersedia,
                valid_count=valid_count,
                salah_total_count=salah_total_count,
                typo_count=typo_count,
                unique_value_info=unique_info,
            )
        )

    sumber_files = (
        sorted(df[SUMBER_FILE_COL].dropna().unique().tolist()) if SUMBER_FILE_COL in df.columns else []
    )
    return MergedValidationResult(total_records=len(df), sumber_files=sumber_files, column_stats=column_stats)


def run_validation_over_data_folder() -> tuple[pd.DataFrame, MergedValidationResult]:
    """Baca+gabungkan semua file di data/, lalu validasi sebagai satu dataset."""
    igt_list = load_igt_list()
    ri_lookup = build_ri_ruleset_lookup(igt_list)
    merged_df = load_and_merge_data_files(list_data_files())
    result = validate_merged_dataframe(merged_df, igt_list, ri_lookup)
    return merged_df, result


@dataclass
class InvalidValueGroup:
    """Satu nilai unik yang salah pada satu kolom IGT — mewakili SEMUA baris yang punya nilai ini."""

    nama_igt: str
    column: str
    nilai_saat_ini: str
    frekuensi: int
    kategori: str
    kandidat: list[dict[str, float | str]] = field(default_factory=list)


def get_invalid_value_groups(
    df: pd.DataFrame,
    igt_list: list[dict] | None = None,
    ri_lookup: dict[str, set[str]] | None = None,
) -> list[InvalidValueGroup]:
    """Daftar nilai unik salah per kolom, siap ditampilkan sebagai satu baris koreksi
    di UI (bukan per record) — mengoreksi satu grup akan berlaku untuk semua baris
    yang punya nilai tsb. Hanya mencakup kolom yang IGT-nya sudah punya ruleset aktif.
    """
    if igt_list is None:
        igt_list = load_igt_list()
    if ri_lookup is None:
        ri_lookup = build_ri_ruleset_lookup(igt_list)

    matches = detect_igt_ri_columns(df.columns, igt_list)
    groups: list[InvalidValueGroup] = []

    for match in matches:
        nama_igt, column = match["nama_igt"], match["column"]
        valid_values = ri_lookup.get(nama_igt)
        if valid_values is None:
            continue

        unique_info = build_unique_value_info(df[column], valid_values)
        for value, info in unique_info.items():
            groups.append(
                InvalidValueGroup(
                    nama_igt=nama_igt,
                    column=column,
                    nilai_saat_ini=value,
                    frekuensi=info["frekuensi"],
                    kategori=info["kategori"],
                    kandidat=info["kandidat"],
                )
            )

    return groups


def apply_value_corrections(
    df: pd.DataFrame, corrections: dict[tuple[str, str], str]
) -> pd.DataFrame:
    """Terapkan koreksi ke SEMUA baris yang cocok, per (kolom, nilai_lama) -> nilai_baru.

    Mengembalikan salinan df yang sudah dikoreksi (df asli tidak diubah).
    """
    corrected = df.copy()
    for (column, nilai_lama), nilai_baru in corrections.items():
        text_series = corrected[column].apply(lambda v: "" if pd.isna(v) else str(v).strip())
        mask = text_series == nilai_lama
        corrected.loc[mask, column] = nilai_baru
    return corrected


def split_and_write_back(corrected_df: pd.DataFrame, base_dir: Path = DATA_DIR) -> dict[str, Path]:
    """Pisahkan dataset gabungan balik ke file asalnya (pakai SUMBER_FILE + _ROW_ASAL)
    dan tulis tiap bagian ke file itu. Mengembalikan {nama_file: path_tersimpan}.
    """
    if SUMBER_FILE_COL not in corrected_df.columns or ROW_ASAL_COL not in corrected_df.columns:
        raise ValueError(
            "DataFrame tidak punya kolom SUMBER_FILE/_ROW_ASAL — bukan hasil load_and_merge_data_files()."
        )

    saved: dict[str, Path] = {}
    for sumber_file, group in corrected_df.groupby(SUMBER_FILE_COL):
        group_sorted = group.sort_values(ROW_ASAL_COL)
        original_columns = [c for c in group_sorted.columns if c not in (SUMBER_FILE_COL, ROW_ASAL_COL)]
        out_df = group_sorted[original_columns].reset_index(drop=True)
        saved[sumber_file] = write_attribute_table(base_dir / sumber_file, out_df)

    return saved


def verify_after_correction(
    df: pd.DataFrame,
    igt_list: list[dict] | None = None,
    ri_lookup: dict[str, set[str]] | None = None,
) -> dict[tuple[str, str], int]:
    """Setelah koreksi diterapkan, hitung berapa nilai UNIK yang masih tidak cocok per kolom.

    Mengembalikan {(nama_igt, column): jumlah_nilai_unik_masih_salah}. Idealnya 0
    untuk kolom yang sudah selesai dikoreksi.
    """
    groups = get_invalid_value_groups(df, igt_list, ri_lookup)
    counts: dict[tuple[str, str], int] = {}
    for group in groups:
        key = (group.nama_igt, group.column)
        counts[key] = counts.get(key, 0) + 1
    return counts


def save_validation_snapshot(result: MergedValidationResult, path: Path | None = None) -> Path:
    """Simpan hasil validasi (termasuk saran koreksi rapidfuzz) ke output/ sebagai JSON."""
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "result": asdict(result),
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


def _style_header_row(worksheet) -> None:
    """Styling sederhana: header bold putih dengan latar biru."""
    bold_white = Font(bold=True, color="FFFFFF")
    fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    for cell in worksheet[1]:
        cell.font = bold_white
        cell.fill = fill


def build_discrepancy_report_excel(result: MergedValidationResult, df: pd.DataFrame) -> bytes:
    """Susun laporan diskrepansi jadi Excel 2 sheet:

    - Ringkasan_Validasi: statistik per kolom (Total Record Checked, Cocok/Valid,
      jumlah Salah Total, jumlah Typo).
    - Perlu_Koreksi_Manual: HANYA baris berkategori Salah Total, dengan kolom
      KOLOM_BERMASALAH dan DETAIL_KATEGORI_ERROR.
    """
    ringkasan_rows = [
        {
            "Nama_IGT": cs.nama_igt,
            "Kolom": cs.column,
            "Ruleset_Tersedia": "Ya" if cs.ruleset_tersedia else "Tidak",
            "Total_Record_Checked": cs.total_checked,
            "Cocok_Valid": cs.valid_count,
            "Salah_Total": cs.salah_total_count,
            "Typo": cs.typo_count,
        }
        for cs in result.column_stats
    ]
    ringkasan_df = pd.DataFrame(
        ringkasan_rows,
        columns=[
            "Nama_IGT",
            "Kolom",
            "Ruleset_Tersedia",
            "Total_Record_Checked",
            "Cocok_Valid",
            "Salah_Total",
            "Typo",
        ],
    )

    manual_rows = []
    for cs in result.column_stats:
        salah_total_values = {
            value for value, info in cs.unique_value_info.items() if info["kategori"] == KATEGORI_SALAH_TOTAL
        }
        if not salah_total_values:
            continue

        text_series = df[cs.column].apply(lambda v: "" if pd.isna(v) else str(v).strip())
        mask = text_series.isin(salah_total_values)
        for idx in df.index[mask]:
            manual_rows.append(
                {
                    "SUMBER_FILE": df.at[idx, SUMBER_FILE_COL] if SUMBER_FILE_COL in df.columns else "-",
                    "Baris": (int(df.at[idx, ROW_ASAL_COL]) if ROW_ASAL_COL in df.columns else int(idx)) + 1,
                    "Nama_IGT": cs.nama_igt,
                    "KOLOM_BERMASALAH": cs.column,
                    "Nilai_Saat_Ini": display_value(text_series.loc[idx]),
                    "DETAIL_KATEGORI_ERROR": KATEGORI_SALAH_TOTAL,
                }
            )

    manual_df = pd.DataFrame(
        manual_rows,
        columns=[
            "SUMBER_FILE",
            "Baris",
            "Nama_IGT",
            "KOLOM_BERMASALAH",
            "Nilai_Saat_Ini",
            "DETAIL_KATEGORI_ERROR",
        ],
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        ringkasan_df.to_excel(writer, index=False, sheet_name="Ringkasan_Validasi")
        manual_df.to_excel(writer, index=False, sheet_name="Perlu_Koreksi_Manual")
        _style_header_row(writer.sheets["Ringkasan_Validasi"])
        _style_header_row(writer.sheets["Perlu_Koreksi_Manual"])
    buffer.seek(0)
    return buffer.getvalue()
