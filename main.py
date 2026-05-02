import glob
import io
import json
import math
import os
import re
import shutil
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path
from typing import List

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from fastapi import FastAPI, File, HTTPException, Response, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from analysis import (
    DataFileRef,
    discover_power_delta_columns,
    find_header_row as smart_find_header_row,
    resolve_data_file,
)


def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


if hasattr(sys, "_MEIPASS"):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_DIR = os.getenv("DATA_DIR", os.path.join(BASE_DIR, "Raw Data"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", os.path.join(BASE_DIR, "uploads"))
TAGS_FILE = os.getenv("TAGS_FILE", os.path.join(BASE_DIR, "config", "tags.json"))
STATIC_DIR = get_resource_path("static")

app = FastAPI(title="OTA Data Comparison")


class GenerateRequest(BaseModel):
    files: List[str]
    includeFailData: bool = False
    channels: List[str] | None = None


class UpdateTagsRequest(BaseModel):
    filename: str
    tags: List[str]


def ensure_runtime_dirs():
    Path(DATA_DIR).mkdir(parents=True, exist_ok=True)
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._~()-]+", "_", name)
    return name or "upload.csv"


def raw_data_filename(filename: str) -> str:
    name = safe_filename(filename)
    if not name.startswith("Organized_"):
        name = f"Organized_{name}"
    return name


def load_tags():
    """Read tags from TAGS_FILE. Returns empty dict if file is missing, a directory, or malformed."""
    tags_path = Path(TAGS_FILE)
    if tags_path.is_file():
        try:
            with tags_path.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading tags: {e}")
    return {}


def save_tags(tags_data):
    """Persist tags to TAGS_FILE. Silently skips if the path is a directory
    (e.g. Docker bind-mount created a dir for a missing source file)."""
    try:
        tags_path = Path(TAGS_FILE)
        if tags_path.is_dir():
            print(f"Warning: {TAGS_FILE} is a directory, cannot save tags")
            return
        tags_path.parent.mkdir(parents=True, exist_ok=True)
        with tags_path.open("w", encoding="utf-8") as f:
            json.dump(tags_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving tags: {e}")


def get_cp_order(cp):
    text = str(cp).strip()
    upper = text.upper()
    if upper == "T0":
        return -2
    if upper == "HS":
        return -1
    match = re.search(r"\d+", text)
    if match:
        return int(match.group())
    return 999


def find_header_row(file_path):
    try:
        return smart_find_header_row(file_path)
    except Exception as e:
        print(f"扫描表头失败: {e}")
        return 7


def source_label(filename: str) -> str:
    return Path(filename).name.replace("Organized_", "").replace(".csv", "")


def file_entry(file_ref: DataFileRef, tags=None):
    source_name = "upload" if file_ref.source_type == "upload" else "raw"
    return {
        "id": file_ref.file_id,
        "name": file_ref.display_name,
        "source": source_name,
        "tags": tags or [],
    }


@app.get("/api/files")
def list_files():
    ensure_runtime_dirs()
    tags_data = load_tags()
    all_tags_set = set()
    files_with_tags = []

    pattern = os.path.join(DATA_DIR, "Organized_*.csv")
    for path in sorted(glob.glob(pattern)):
        name = os.path.basename(path)
        f_tags = tags_data.get(name, [])
        all_tags_set.update(f_tags)
        ref = resolve_data_file(f"raw:{name}", DATA_DIR, UPLOAD_DIR)
        files_with_tags.append(file_entry(ref, f_tags))

    upload_pattern = os.path.join(UPLOAD_DIR, "*.csv")
    for path in sorted(glob.glob(upload_pattern)):
        name = os.path.basename(path)
        ref = resolve_data_file(f"upload:{name}", DATA_DIR, UPLOAD_DIR)
        files_with_tags.append(file_entry(ref, ["Uploaded"]))
        all_tags_set.add("Uploaded")

    return {"files": files_with_tags, "all_tags": sorted(all_tags_set)}


@app.post("/api/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    ensure_runtime_dirs()
    uploaded = []

    for upload in files:
        original_name = safe_filename(upload.filename or "upload.csv")
        if not original_name.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"{original_name} 不是 CSV 文件")

        target_name = f"{uuid.uuid4().hex[:8]}_{original_name}"
        target_path = Path(UPLOAD_DIR) / target_name
        with target_path.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)

        ref = resolve_data_file(f"upload:{target_name}", DATA_DIR, UPLOAD_DIR)
        uploaded.append(file_entry(ref, ["Uploaded"]))

    return {"uploaded": uploaded}


@app.post("/api/rawdata/upload")
async def upload_raw_data_files(files: List[UploadFile] = File(...)):
    ensure_runtime_dirs()
    uploaded = []
    tags_data = load_tags()

    for upload in files:
        original_name = raw_data_filename(upload.filename or "rawdata.csv")
        if not original_name.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"{original_name} 不是 CSV 文件")

        target_path = Path(DATA_DIR) / original_name
        if target_path.exists():
            stem = target_path.stem
            suffix = target_path.suffix
            original_name = f"{stem}_{uuid.uuid4().hex[:8]}{suffix}"
            target_path = Path(DATA_DIR) / original_name

        with target_path.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)

        tags_data.setdefault(original_name, ["RawData"])
        ref = resolve_data_file(f"raw:{original_name}", DATA_DIR, UPLOAD_DIR)
        uploaded.append(file_entry(ref, tags_data[original_name]))

    save_tags(tags_data)
    return {"uploaded": uploaded}


@app.post("/api/tags")
def update_file_tags(request: UpdateTagsRequest):
    if request.filename.startswith("upload:"):
        raise HTTPException(status_code=400, detail="上传文件暂不保存标签")
    filename = request.filename.removeprefix("raw:")
    tags_data = load_tags()
    tags_data[filename] = request.tags
    save_tags(tags_data)
    return {"status": "success"}


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


def process_file(filename: str, include_fail_data: bool, selected_channels: set[str] | None):
    ref = resolve_data_file(filename, DATA_DIR, UPLOAD_DIR)
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
        header_idx = find_header_row(ref.path)
        df_cols = pd.read_csv(ref.path, skiprows=header_idx, nrows=0)
        matches = discover_power_delta_columns(df_cols.columns)
        if selected_channels:
            matches = {k: v for k, v in matches.items() if k in selected_channels}

        if not matches:
            report["message"] = "未识别到 Tx Power Delta 频点列"
            return None, report

        df = pd.read_csv(ref.path, skiprows=header_idx)
        if not include_fail_data:
            df = filter_pass_records(df)

        df = normalize_columns(df)
        if "CheckPoint" not in df.columns or "SerialNumber" not in df.columns:
            report["message"] = "缺少 CheckPoint/CP 或 SerialNumber 列"
            return None, report

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
        df_melted["Channel"] = df_melted["Full_Test"].map(lambda x: by_column[x].channel)
        df_melted["Frequency"] = df_melted["Full_Test"].map(lambda x: by_column[x].frequency)
        df_melted["Source"] = source_label(ref.display_name)
        df_melted["SourceType"] = ref.source_type
        df_melted["Delta"] = pd.to_numeric(df_melted["Delta"], errors="coerce")
        df_melted = df_melted.dropna(subset=["Delta", "CheckPoint"])

        report["status"] = "ok"
        report["rows"] = int(len(df_melted))
        report["matched_channels"] = sorted({match.channel for match in matches.values()})
        report["frequencies"] = sorted({match.frequency for match in matches.values()})
        report["message"] = "OK"
        return df_melted, report
    except Exception as e:
        report["message"] = f"读取失败: {e}"
        return None, report


def get_cleaned_data(files: List[str], includeFailData: bool = False, channels: List[str] | None = None):
    all_dfs = []
    reports = []
    selected_channels = set(channels) if channels else None

    for filename in files:
        df_melted, report = process_file(filename, includeFailData, selected_channels)
        reports.append(report)
        if df_melted is not None and not df_melted.empty:
            all_dfs.append(df_melted)

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
    raw_unique_cps = full_df["CheckPoint"].unique()
    unique_cps = sorted(
        [
            cp
            for cp in raw_unique_cps
            if pd.notna(cp) and str(cp).lower() != "nan" and str(cp).strip() != ""
        ],
        key=get_cp_order,
    )
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


@app.post("/api/fetch_chart_data")
def fetch_chart_data(request: GenerateRequest):
    full_df, unique_cps, reports, summary = get_cleaned_data(
        request.files, request.includeFailData, request.channels
    )
    if full_df is None:
        raise HTTPException(status_code=400, detail={"message": "所选文件无有效数据", "reports": reports})

    sources = list(full_df["Source"].unique())
    if len(sources) > 10:
        sources = sources[:10]
        full_df = full_df[full_df["Source"].isin(sources)]

    data_records = full_df.replace({math.nan: None, math.inf: None, -math.inf: None}).to_dict(
        orient="records"
    )

    return {
        "data": data_records,
        "unique_cps": unique_cps,
        "sources": sources,
        "summary": summary,
        "file_reports": reports,
        "available_channels": sorted(full_df["Channel"].dropna().unique().tolist()),
        "available_frequencies": sorted(full_df["Frequency"].dropna().unique().tolist()),
    }


@app.post("/api/generate")
def generate_chart(request: GenerateRequest):
    full_df, unique_cps, reports, _summary = get_cleaned_data(
        request.files, request.includeFailData, request.channels
    )
    if full_df is None:
        raise HTTPException(status_code=400, detail="所选文件无有效数据可以用于绘图")

    sources = full_df["Source"].unique()
    n_sources = len(sources)
    n_cp = len(unique_cps)

    if n_sources > 10:
        sources = sources[:10]
        full_df = full_df[full_df["Source"].isin(sources)]
        n_sources = 10

    base_box_width = 0.108
    min_box_width = 0.05
    cp_margin = 0.072

    if n_sources == 1:
        single_box_width = base_box_width
        group_width_physical = single_box_width
        sns_gap = 0.0
    else:
        single_box_width = base_box_width - (base_box_width - min_box_width) * (n_sources - 1) / 9.0
        sns_gap = 0.1
        element_physical_width = single_box_width / (1 - sns_gap)
        group_width_physical = n_sources * element_physical_width

    cp_total_width = group_width_physical + cp_margin
    sns_width = group_width_physical / cp_total_width

    calculated_width = max(8.0, cp_total_width * n_cp)
    font_calc_width = min(calculated_width, 20.0)
    dynamic_fontsize = max(8, min(12, int(font_calc_width / 1.2)))
    title_fontsize = max(16, min(26, int(font_calc_width * 1.8)))

    if n_sources <= 4:
        box_lw, median_lw, whisker_lw = 1.5, 1.0, 0.6
    else:
        box_lw, median_lw, whisker_lw = 1.0, 0.8, 0.4

    custom_palette = [
        "#0000FF",
        "#FF0000",
        "#00CC00",
        "#FF00FF",
        "#FF9900",
        "#00FFFF",
        "#9900CC",
        "#FF007F",
        "#00FF00",
        "#008080",
    ]
    if n_sources == 2:
        custom_palette = ["#0000FF", "#FF0000"]

    plt.rcParams["font.sans-serif"] = ["Arial", "sans-serif"]
    channels = request.channels or ["Tx_LC", "Tx_MC", "Tx_HC"]
    channels = [ch for ch in channels if ch in full_df["Channel"].unique()]
    fig, axes = plt.subplots(len(channels), 1, figsize=(calculated_width, 6.5 * len(channels)), sharex=True)
    if len(channels) == 1:
        axes = [axes]
    plt.subplots_adjust(hspace=0.0)

    g_min, g_max = full_df["Delta"].min(), full_df["Delta"].max()
    padding = (g_max - g_min) * 0.05 if (g_max - g_min) != 0 else 1
    y_min, y_max = math.floor(g_min - padding), math.ceil(g_max + padding)
    y_min, y_max = min(y_min, -6), max(y_max, 0)
    if y_min % 2 != 0:
        y_min -= 1
    if y_max % 2 != 0:
        y_max += 1

    for i, ch in enumerate(channels):
        ax = axes[i]
        ch_data = full_df[full_df["Channel"] == ch]
        sns.boxplot(
            data=ch_data,
            x="CheckPoint",
            y="Delta",
            hue="Source",
            ax=ax,
            palette=custom_palette[:n_sources],
            showfliers=False,
            dodge=True,
            width=sns_width,
            gap=sns_gap,
            linewidth=box_lw,
            whis=[0, 100],
            showcaps=False,
            boxprops={"edgecolor": "none"},
            medianprops={"color": "white", "linewidth": median_lw},
            fliersize=0,
        )

        all_children = ax.get_children()
        rects_info = []
        for child in all_children:
            if isinstance(child, patches.PathPatch):
                path = child.get_path()
                vertices = path.vertices
                if len(vertices) > 0:
                    rx = (vertices[:, 0].max() + vertices[:, 0].min()) / 2
                    rects_info.append({"x": rx, "color": child.get_facecolor()})

        for child in all_children:
            if isinstance(child, plt.Line2D):
                xdata, ydata = child.get_xdata(), child.get_ydata()
                if len(xdata) == 2 and abs(xdata[0] - xdata[1]) < 0.001 and ydata[0] != ydata[1]:
                    lx = xdata[0]
                    for r_info in rects_info:
                        if abs(lx - r_info["x"]) < 0.1:
                            child.set_color(r_info["color"])
                            child.set_linewidth(whisker_lw)
                            child.set_zorder(5)
                            break

        ax.axhline(y=-6, color="#FF0000", linestyle="--", linewidth=1.5, zorder=10)
        ax.axhline(y=0, color="gray", linewidth=0.5, alpha=0.5)
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("black")
            spine.set_linewidth(1.0)
        ax.set_ylim(y_min, y_max)
        ticks = [t for t in range(int(y_min), int(y_max) + 1, 2)]
        ax.set_yticks(ticks)
        ax.set_yticklabels([str(t) for t in ticks])
        ax.set_ylabel(ch, fontsize=14, fontweight="bold", labelpad=15)
        ax.grid(False)
        ax.set_facecolor("white")
        if i == 0:
            ax.set_title("Tx power drop", fontsize=title_fontsize, fontweight="bold", pad=20, loc="left")
            ax.legend(
                title="",
                bbox_to_anchor=(1.0, 1.02),
                loc="lower right",
                frameon=False,
                fontsize=dynamic_fontsize,
                ncol=1,
                labelspacing=0.2,
                handletextpad=0.5,
            )
        elif ax.get_legend():
            ax.get_legend().remove()

    plt.xlabel("CP", fontsize=14, fontweight="bold", labelpad=15)
    plt.xticks(rotation=45, ha="right", fontsize=dynamic_fontsize)

    unique_sources = list(full_df["Source"].unique())
    short_sources = ["-".join(s.split("-")[:3]) for s in unique_sources]
    build_suffix = short_sources[0] if len(short_sources) == 1 else "_vs_".join(short_sources)

    output_name = f"OTA_JMP_{build_suffix}.png"
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)

    headers = {
        "Content-Disposition": f'inline; filename="{output_name}"',
        "X-Filename": output_name,
        "Access-Control-Expose-Headers": "X-Filename",
    }
    return Response(content=buf.getvalue(), media_type="image/png", headers=headers)


def open_browser():
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    if os.getenv("OPEN_BROWSER", "0") == "1":
        threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host=host, port=port)
