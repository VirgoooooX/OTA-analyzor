import re
from collections import defaultdict
from functools import cmp_to_key
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


def _insert_before(sequence: list[str], anchor: str, items: list[str]) -> list[str]:
    if not items:
        return sequence
    index = sequence.index(anchor)
    return sequence[:index] + items + sequence[index:]


def _insert_after(sequence: list[str], anchor: str, items: list[str]) -> list[str]:
    if not items:
        return sequence
    index = sequence.index(anchor) + 1
    return sequence[:index] + items + sequence[index:]


STRUCTURED_CHECKPOINT_RE = re.compile(
    r"^(left|right|top|bottom)\s*[-_ ]*\s*(\d+(?:\.\d+)?)$",
    re.IGNORECASE,
)


def parse_structured_checkpoint(cp: str) -> tuple[str, float] | None:
    match = STRUCTURED_CHECKPOINT_RE.match(str(cp).strip())
    if not match:
        return None
    group = match.group(1).lower()
    value = float(match.group(2))
    return group, value


def _is_strong_majority(support: int, against: int) -> bool:
    return support >= 3 or (support >= 2 and against == 0)


def _merge_checkpoint_sequences_by_anchor(sequences) -> list[str]:
    normalized = []
    for index, sequence in enumerate(sequences):
        ordered = ordered_checkpoints(sequence)
        if ordered:
            normalized.append((index, ordered))

    if not normalized:
        return []

    # Prefer the richest sequence as the merge backbone.
    normalized.sort(key=lambda item: (-len(item[1]), item[0]))
    merged = list(normalized[0][1])

    for _index, sequence in normalized[1:]:
        anchors = [cp for cp in sequence if cp in merged]
        missing = [cp for cp in sequence if cp not in merged]
        if not missing:
            continue
        if not anchors:
            merged.extend(missing)
            continue

        anchor_positions = [i for i, cp in enumerate(sequence) if cp in merged]
        first_anchor_pos = anchor_positions[0]
        first_anchor = sequence[first_anchor_pos]
        merged = _insert_before(
            merged,
            first_anchor,
            [cp for cp in sequence[:first_anchor_pos] if cp not in merged],
        )

        for left_pos, right_pos in zip(anchor_positions, anchor_positions[1:]):
            left_anchor = sequence[left_pos]
            between = [cp for cp in sequence[left_pos + 1:right_pos] if cp not in merged]
            merged = _insert_after(merged, left_anchor, between)

        last_anchor_pos = anchor_positions[-1]
        last_anchor = sequence[last_anchor_pos]
        merged = _insert_after(
            merged,
            last_anchor,
            [cp for cp in sequence[last_anchor_pos + 1:] if cp not in merged],
        )

    return merged


def _collect_pairwise_counts(sequences: list[list[str]]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for sequence in sequences:
        ordered = ordered_checkpoints(sequence)
        for i, left in enumerate(ordered):
            for right in ordered[i + 1:]:
                counts[(left, right)] += 1
    return dict(counts)


def _build_structured_groups(items: list[str]) -> dict[str, list[tuple[float, str]]]:
    groups: dict[str, list[tuple[float, str]]] = defaultdict(list)
    for item in items:
        parsed = parse_structured_checkpoint(item)
        if parsed is None:
            continue
        group, value = parsed
        groups[group].append((value, item))
    for group_items in groups.values():
        group_items.sort(key=lambda entry: (entry[0], entry[1]))
    return dict(groups)


def _build_hard_edges(
    items: list[str],
    pair_counts: dict[tuple[str, str], int],
    structured_groups: dict[str, list[tuple[float, str]]],
) -> dict[str, set[str]]:
    edges: dict[str, set[str]] = {item: set() for item in items}

    for i, left in enumerate(items):
        for right in items[i + 1:]:
            forward = pair_counts.get((left, right), 0)
            backward = pair_counts.get((right, left), 0)
            if forward == backward:
                continue
            if forward > backward and _is_strong_majority(forward, backward):
                edges[left].add(right)
            elif backward > forward and _is_strong_majority(backward, forward):
                edges[right].add(left)

    for group_items in structured_groups.values():
        for (left_value, left_cp), (right_value, right_cp) in zip(group_items, group_items[1:]):
            if left_value == right_value:
                continue
            forward = pair_counts.get((left_cp, right_cp), 0)
            backward = pair_counts.get((right_cp, left_cp), 0)
            if _is_strong_majority(backward, forward):
                continue
            edges[left_cp].add(right_cp)

    return edges


def _compare_checkpoint_priority(
    left: str,
    right: str,
    pair_counts: dict[tuple[str, str], int],
    backbone_index: dict[str, int],
) -> int:
    forward = pair_counts.get((left, right), 0)
    backward = pair_counts.get((right, left), 0)
    if forward != backward:
        support = max(forward, backward)
        against = min(forward, backward)
        if forward > backward:
            if _is_strong_majority(forward, backward):
                return -1
            if support > against:
                return -1
        else:
            if _is_strong_majority(backward, forward):
                return 1
            if support > against:
                return 1

    left_structured = parse_structured_checkpoint(left)
    right_structured = parse_structured_checkpoint(right)
    if left_structured and right_structured and left_structured[0] == right_structured[0]:
        left_value = left_structured[1]
        right_value = right_structured[1]
        if left_value != right_value:
            if left_value < right_value:
                if not _is_strong_majority(backward, forward):
                    return -1
            else:
                if not _is_strong_majority(forward, backward):
                    return 1

    left_index = backbone_index[left]
    right_index = backbone_index[right]
    if left_index < right_index:
        return -1
    if left_index > right_index:
        return 1
    return -1 if left < right else 1


def _build_priority_order(items: list[str], pair_counts: dict[tuple[str, str], int]) -> list[str]:
    backbone_index = {item: index for index, item in enumerate(items)}
    return sorted(
        items,
        key=cmp_to_key(
            lambda left, right: _compare_checkpoint_priority(left, right, pair_counts, backbone_index)
        ),
    )


def _stable_topological_order(
    items: list[str],
    edges: dict[str, set[str]],
    priority_order: list[str],
) -> list[str]:
    remaining = set(items)
    indegree = {item: 0 for item in items}
    for sources in edges.values():
        for target in sources:
            indegree[target] += 1

    priority_index = {item: index for index, item in enumerate(priority_order)}
    ordered = []

    while remaining:
        available = [item for item in remaining if indegree[item] == 0]
        if not available:
            available = list(remaining)
        available.sort(key=lambda item: (priority_index[item], item))
        chosen = available[0]
        ordered.append(chosen)
        remaining.remove(chosen)
        for target in edges[chosen]:
            indegree[target] -= 1

    return ordered


def merge_checkpoint_sequences(sequences) -> list[str]:
    normalized = [ordered_checkpoints(sequence) for sequence in sequences if ordered_checkpoints(sequence)]
    if not normalized:
        return []

    backbone = _merge_checkpoint_sequences_by_anchor(normalized)
    pair_counts = _collect_pairwise_counts(normalized)
    structured_groups = _build_structured_groups(backbone)
    hard_edges = _build_hard_edges(backbone, pair_counts, structured_groups)
    priority_order = _build_priority_order(backbone, pair_counts)
    return _stable_topological_order(backbone, hard_edges, priority_order)


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
