import re
from pathlib import Path

from analysis import DataFileRef, find_header_row as smart_find_header_row


def ensure_runtime_dirs(data_dir, upload_dir):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    Path(upload_dir).mkdir(parents=True, exist_ok=True)


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip().replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._~()-]+", "_", name)
    return name or "upload.csv"


def raw_data_filename(filename: str) -> str:
    name = safe_filename(filename)
    if not name.startswith("Organized_"):
        name = f"Organized_{name}"
    return name


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


def ordered_checkpoints(values) -> list[str]:
    ordered = []
    seen = set()

    for value in values:
        if value is None:
            continue
        cp = str(value).strip()
        if not cp or cp.lower() == "nan":
            continue
        if cp in seen:
            continue
        seen.add(cp)
        ordered.append(cp)

    return ordered


def find_header_row(file_path):
    try:
        return smart_find_header_row(file_path)
    except Exception as e:
        print(f"扫描表头失败: {e}")
        return 7


def source_label(filename: str) -> str:
    return Path(filename).name.replace("Organized_", "").replace(".csv", "")


def file_entry(file_ref: DataFileRef, tags=None, metadata=None, parsed=None):
    source_name = "upload" if file_ref.source_type == "upload" else "raw"
    entry = {
        "id": file_ref.file_id,
        "name": file_ref.display_name,
        "source": source_name,
        "tags": tags or [],
    }
    if metadata:
        entry["metadata"] = metadata
    if parsed:
        entry["parsed"] = parsed
    return entry
