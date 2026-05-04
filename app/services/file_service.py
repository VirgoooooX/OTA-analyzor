import glob
import os

import pandas as pd

from analysis import resolve_data_file, discover_power_delta_columns
from app.config import DATA_DIR, UPLOAD_DIR
from app.database import get_file_cache, set_file_cache, get_file_metadata, set_file_metadata
from app.services.filename_parser import parse_filename
from app.services.tag_service import list_all_tags
from app.utils import find_header_row, file_entry


def extract_metadata(file_path: str) -> dict:
    """Lightweight metadata extraction from a CSV file."""
    try:
        header_idx = find_header_row(file_path)
        df_cols = pd.read_csv(file_path, skiprows=header_idx, nrows=0)
        matches = discover_power_delta_columns(df_cols.columns)

        df = pd.read_csv(file_path, skiprows=header_idx)
        row_count = len(df)

        sn_col = next(
            (c for c in df.columns if str(c).lower() in ["serialnumber", "serial number", "sn"]),
            None,
        )
        cp_col = next(
            (c for c in df.columns if str(c).lower() in ["checkpoint", "cp"]),
            None,
        )
        sn_count = int(df[sn_col].nunique()) if sn_col else 0
        unique_cps = sorted(df[cp_col].dropna().unique().tolist()) if cp_col else []

        return {
            "row_count": row_count,
            "sn_count": sn_count,
            "channels": sorted({m.channel for m in matches.values()}),
            "frequencies": sorted({m.frequency for m in matches.values()}),
            "unique_cps": unique_cps,
        }
    except Exception as e:
        return {
            "row_count": 0,
            "sn_count": 0,
            "channels": [],
            "frequencies": [],
            "unique_cps": [],
        }


def get_cached_or_extract(file_path: str) -> dict | None:
    """Return cached metadata if file mtime matches, otherwise extract and cache."""
    try:
        mtime = os.path.getmtime(file_path)
    except OSError:
        return None

    cached = get_file_cache(file_path, mtime)
    if cached is not None:
        return cached

    metadata = extract_metadata(file_path)
    set_file_cache(file_path, mtime, metadata)
    return metadata


def get_cached_or_parse_filename(filename: str) -> dict:
    """Return cached parsed filename metadata, or parse and cache it."""
    cached = get_file_metadata(filename)
    if cached is not None:
        return cached
    parsed = parse_filename(filename)
    set_file_metadata(filename, parsed)
    return parsed


def list_files() -> dict:
    """Scan data and upload dirs, return {files, all_tags} with cached metadata."""
    tags_data, all_tags = list_all_tags()
    all_tags_set = set(all_tags)
    files_with_tags = []

    # Raw Data files
    pattern = os.path.join(str(DATA_DIR), "Organized_*.csv")
    for path in sorted(glob.glob(pattern)):
        name = os.path.basename(path)
        f_tags = tags_data.get(name, [])
        all_tags_set.update(f_tags)
        ref = resolve_data_file(f"raw:{name}", str(DATA_DIR), str(UPLOAD_DIR))
        metadata = get_cached_or_extract(str(ref.path))
        parsed = get_cached_or_parse_filename(name)
        files_with_tags.append(file_entry(ref, f_tags, metadata, parsed))

    # Uploaded files
    upload_pattern = os.path.join(str(UPLOAD_DIR), "*.csv")
    for path in sorted(glob.glob(upload_pattern)):
        name = os.path.basename(path)
        all_tags_set.add("Uploaded")
        ref = resolve_data_file(f"upload:{name}", str(DATA_DIR), str(UPLOAD_DIR))
        metadata = get_cached_or_extract(str(ref.path))
        parsed = get_cached_or_parse_filename(name)
        files_with_tags.append(file_entry(ref, ["Uploaded"], metadata, parsed))

    return {"files": files_with_tags, "all_tags": sorted(all_tags_set)}
