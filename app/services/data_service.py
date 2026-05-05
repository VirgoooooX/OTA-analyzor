import math
import os

import pandas as pd

from analysis import resolve_data_file, discover_power_delta_columns, discover_raw_power_columns
from app.config import DATA_DIR, UPLOAD_DIR
from app.utils import find_header_row, source_label, ordered_checkpoints


def normalize_columns(df: pd.DataFrame):
    rename_map = {}
    for column in df.columns:
        lowered = str(column).strip().lower()
        if lowered in ["checkpoint", "cp"]:
            rename_map[column] = "CheckPoint"
        elif lowered in ["serialnumber", "serial number", "sn"]:
            rename_map[column] = "SerialNumber"
    return df.rename(columns=rename_map)


def filter_pass_records(df: pd.DataFrame):
    status_col = next(
        (
            c
            for c in df.columns
            if "pass/fail" in str(c).lower() or "status" in str(c).lower()
        ),
        None,
    )
    if not status_col:
        return df

    cp_col = next((c for c in df.columns if str(c).lower() in ["checkpoint", "cp"]), None)
    sn_col = next((c for c in df.columns if str(c).lower() in ["serialnumber", "serial number", "sn"]), None)

    if cp_col and sn_col:
        time_col = next((c for c in df.columns if "endtime" in str(c).lower()), None)
        if not time_col:
            time_col = next((c for c in df.columns if "starttime" in str(c).lower()), None)
        if time_col:
            try:
                df[time_col] = pd.to_datetime(df[time_col], errors="coerce", format="mixed")
            except (TypeError, ValueError):
                df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
            df = df.sort_values(by=time_col)

        def filter_group(g):
            passes = g[g[status_col].astype(str).str.upper() == "PASS"]
            if not passes.empty:
                return passes
            return g.tail(1)

        try:
            return df.groupby([sn_col, cp_col], group_keys=False).apply(
                filter_group, include_groups=True
            )
        except TypeError:
            return df.groupby([sn_col, cp_col], group_keys=False).apply(filter_group)

    return df[df[status_col].astype(str).str.upper() == "PASS"]


def process_file(filename: str, include_fail_data: bool, selected_channels: set | None, data_type: str = "delta"):
    ref = resolve_data_file(filename, str(DATA_DIR), str(UPLOAD_DIR))
    report = {
        "id": ref.file_id,
        "name": ref.display_name,
        "source": ref.source_type,
        "status": "skipped",
        "rows": 0,
        "matched_channels": [],
        "frequencies": [],
        "message": "",
    }

    if not ref.path.exists():
        report["message"] = "文件不存在"
        return None, report

    try:
        header_idx = find_header_row(str(ref.path))
        df_cols = pd.read_csv(str(ref.path), skiprows=header_idx, nrows=0)
        if data_type == "raw":
            matches = discover_raw_power_columns(df_cols.columns)
        else:
            matches = discover_power_delta_columns(df_cols.columns)
        if selected_channels:
            matches = {k: v for k, v in matches.items() if k in selected_channels}

        if not matches:
            label = "Raw Power" if data_type == "raw" else "Tx Power Delta"
            report["message"] = f"未识别到 {label} 频点列"
            return None, report

        df = pd.read_csv(str(ref.path), skiprows=header_idx)
        df = normalize_columns(df)
        if "CheckPoint" not in df.columns or "SerialNumber" not in df.columns:
            report["message"] = "缺少 CheckPoint/CP 或 SerialNumber 列"
            return None, report, []

        cp_sequence = ordered_checkpoints(df["CheckPoint"].tolist())

        if not include_fail_data:
            df = filter_pass_records(df)

        value_columns = [match.column for match in matches.values()]
        needed_cols = ["CheckPoint", "SerialNumber"] + value_columns
        df_subset = df[needed_cols].copy()
        df_melted = df_subset.melt(
            id_vars=["CheckPoint", "SerialNumber"],
            value_vars=value_columns,
            var_name="Full_Test",
            value_name="Delta",
        )

        by_column = {match.column: match for match in matches.values()}
        df_melted["Channel"] = df_melted["Full_Test"].map(lambda x: by_column[x].channel if x in by_column else None)
        df_melted["Frequency"] = df_melted["Full_Test"].map(lambda x: by_column[x].frequency if x in by_column else None)
        df_melted["Source"] = source_label(ref.display_name)
        df_melted["SourceType"] = ref.source_type
        df_melted["Delta"] = pd.to_numeric(df_melted["Delta"], errors="coerce")
        df_melted = df_melted.dropna(subset=["Delta", "CheckPoint"])

        report["status"] = "ok"
        report["rows"] = int(len(df_melted))
        report["matched_channels"] = sorted({match.channel for match in matches.values()})
        report["frequencies"] = sorted({match.frequency for match in matches.values()})
        report["message"] = "OK"
        return df_melted, report, cp_sequence
    except Exception as e:
        report["message"] = f"读取失败: {e}"
        return None, report, []


def get_cleaned_data(files: list, include_fail_data: bool = False, channels: list | None = None, data_type: str = "delta"):
    all_dfs = []
    cp_sequence = []
    reports = []
    selected_channels = set(channels) if channels else None

    for filename in files:
        df_melted, report, file_cp_sequence = process_file(
            filename, include_fail_data, selected_channels, data_type
        )
        reports.append(report)
        if df_melted is not None and not df_melted.empty:
            all_dfs.append(df_melted)
        cp_sequence.extend(file_cp_sequence)

    if not all_dfs:
        return None, None, reports, {
            "total_files": len(files),
            "valid_files": 0,
            "skipped_files": len(files),
            "rows": 0,
            "warnings": [r["message"] for r in reports if r["message"] and r["message"] != "OK"],
        }

    full_df = pd.concat(all_dfs).dropna(subset=["Delta", "CheckPoint"])
    full_df["CheckPoint"] = full_df["CheckPoint"].astype(str)
    valid_cps = set(ordered_checkpoints(full_df["CheckPoint"].tolist()))
    unique_cps = [cp for cp in ordered_checkpoints(cp_sequence) if cp in valid_cps]
    full_df["CheckPoint"] = pd.Categorical(full_df["CheckPoint"], categories=unique_cps, ordered=True)

    valid_reports = [r for r in reports if r["status"] == "ok"]
    warnings = [r["message"] for r in reports if r["status"] != "ok" and r["message"]]
    summary = {
        "total_files": len(files),
        "valid_files": len(valid_reports),
        "skipped_files": len(files) - len(valid_reports),
        "rows": int(len(full_df)),
        "warnings": warnings,
    }

    return full_df, unique_cps, reports, summary
