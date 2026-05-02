import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class DataFileRef:
    path: Path
    source_type: str
    display_name: str
    file_id: str


@dataclass(frozen=True)
class DeltaColumnMatch:
    column: str
    frequency: str
    channel: str
    score: int


def find_header_row(file_path: str | Path, scan_limit: int = 80) -> int:
    path = Path(file_path)
    best_index = 7
    best_score = 0

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for index, line in enumerate(handle):
            lowered = line.lower()
            score = 0
            if "serialnumber" in lowered or "serial number" in lowered:
                score += 4
            if "checkpoint" in lowered or re.search(r"(^|,)cp($|,)", lowered):
                score += 4
            if "pass/fail" in lowered or "status" in lowered:
                score += 1
            if "freq=" in lowered:
                score += 1
            if "delta" in lowered:
                score += 1

            if score > best_score:
                best_index = index
                best_score = score

            if score >= 8:
                return index
            if index >= scan_limit:
                break

    return best_index


def parse_test_column(column: str) -> dict[str, str | bool]:
    text = str(column)
    lowered = text.lower()
    freq_match = re.search(r"freq\s*=\s*(\d+)", lowered)
    tc_match = re.search(r"(?:^|[:\s])tc\s*=\s*([^:\s]+)", lowered)

    return {
        "frequency": freq_match.group(1) if freq_match else "",
        "test_class": tc_match.group(1) if tc_match else "",
        "is_delta": "delta" in lowered,
        "is_power": "power" in lowered,
        "is_bt": "bt" in lowered,
    }


def channel_for_frequency(frequency: str | int) -> str | None:
    try:
        freq = int(frequency)
    except (TypeError, ValueError):
        return None

    if freq <= 2420:
        return "Tx_LC"
    if 2430 <= freq <= 2455:
        return "Tx_MC"
    if freq >= 2470:
        return "Tx_HC"
    return None


def discover_power_delta_columns(columns: Iterable[str]) -> dict[str, DeltaColumnMatch]:
    best_by_channel: dict[str, DeltaColumnMatch] = {}

    for column in columns:
        parsed = parse_test_column(column)
        frequency = str(parsed["frequency"])
        channel = channel_for_frequency(frequency)
        if not channel:
            continue

        score = 0
        if parsed["is_delta"]:
            score += 5
        if parsed["is_power"]:
            score += 4
        if parsed["is_bt"]:
            score += 1
        if parsed["test_class"] == "power":
            score += 2

        if score < 6:
            continue

        candidate = DeltaColumnMatch(
            column=str(column),
            frequency=frequency,
            channel=channel,
            score=score,
        )
        current = best_by_channel.get(channel)
        if current is None or candidate.score > current.score:
            best_by_channel[channel] = candidate

    return best_by_channel


def resolve_data_file(file_id: str, data_dir: str | Path, upload_dir: str | Path) -> DataFileRef:
    data_path = Path(data_dir)
    upload_path = Path(upload_dir)

    if file_id.startswith("upload:"):
        name = Path(file_id.removeprefix("upload:")).name
        path = upload_path / name
        source_type = "upload"
        resolved_id = f"upload:{name}"
    else:
        name = Path(file_id).name
        path = data_path / name
        source_type = "server"
        resolved_id = name

    return DataFileRef(
        path=path,
        source_type=source_type,
        display_name=name,
        file_id=resolved_id,
    )
