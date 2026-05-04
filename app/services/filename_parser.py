"""Parse OTA CSV filenames into structured metadata fields.

Handles two main naming patterns:

Standard:  Organized_{Project}-{Build}_{CFG}-{PreCond}-{Checkpoint}-OTA_Data[...].csv
Legacy:    Organized_{CFG} Drop {Height} [...].csv
"""

import re

# Pre-compiled patterns
_NOISE_SUFFIXES = re.compile(
    r"[-_ ]*(?:OTA_Data|BT-OTA-[\d.]+|_?RX_Processed)"
    r"(?:[-_ ]*\d+)?",          # trailing " 2" in some filenames
    re.IGNORECASE,
)

_CHECKPOINT_RE = re.compile(
    r"(?:Drop|Dorp)\s*(\d+)|Top\s*(\d+)",  # "Dorp" is a known typo
    re.IGNORECASE,
)

_PRECONDITION_RE = re.compile(
    r"\b(NonHS|4[- ]Corner)\b|(?<![A-Za-z])(HS)(?![A-Za-z])",
    re.IGNORECASE,
)

_PROJECT_BUILD_RE = re.compile(
    r"^(B\d+\w*)[- ](EVT|POR|DVT|PVT|MP|P\d+)[_ ]",
    re.IGNORECASE,
)

_EXTRAS = ["Plinko", "Relbot", "Granite", "PB", "w dwell", "HSD"]


def parse_filename(filename: str) -> dict:
    """Extract structured metadata from an OTA CSV filename.

    Returns dict with keys: project, build, cfg, precondition,
    checkpoint, test_item, extra, display_parts (list of non-empty
    segments for the UI display line).
    """
    result = {
        "project": "",
        "build": "",
        "cfg": "",
        "precondition": "",
        "checkpoint": "",
        "test_item": "",
        "extra": "",
    }

    # Strip prefix and extension
    name = filename
    if name.lower().startswith("organized_"):
        name = name[len("Organized_"):]
    if name.lower().endswith(".csv"):
        name = name[:-4]

    # Strip noise suffixes (OTA_Data, BT-OTA-x.x.x, RX_Processed, etc.)
    cleaned = _NOISE_SUFFIXES.sub("", name).strip(" -_")

    # ── Extract checkpoint (Drop/Top) ──
    cp_match = _CHECKPOINT_RE.search(cleaned)
    if cp_match:
        drop_val = cp_match.group(1)
        top_val = cp_match.group(2)
        if drop_val:
            result["checkpoint"] = f"Drop{drop_val}"
            result["test_item"] = "Random Drop"
        else:
            result["checkpoint"] = f"Top{top_val}"
            result["test_item"] = "HSD"
        # Remove checkpoint from cleaned string for further parsing
        cleaned = cleaned[:cp_match.start()] + cleaned[cp_match.end():]
        cleaned = cleaned.strip(" -_")

    # ── Extract pre-condition (HS / NonHS / 4-Corner) ──
    pc_match = _PRECONDITION_RE.search(cleaned)
    if pc_match:
        raw_pc = pc_match.group(1) or pc_match.group(2)
        result["precondition"] = _normalize_precondition(raw_pc)
        cleaned = cleaned[:pc_match.start()] + cleaned[pc_match.end():]
        cleaned = cleaned.strip(" -_")

    # ── Extract extra descriptors ──
    extras_found = []
    for extra in _EXTRAS:
        pattern = re.compile(re.escape(extra), re.IGNORECASE)
        if pattern.search(cleaned):
            extras_found.append(extra)
            cleaned = pattern.sub("", cleaned).strip(" -_")
    if extras_found:
        # Remove "HSD" from extras if test_item is already HSD
        if result["test_item"] == "HSD" and "HSD" in extras_found:
            extras_found.remove("HSD")
        result["extra"] = " ".join(extras_found) if extras_found else ""

    # ── Extract project and build ──
    pb_match = _PROJECT_BUILD_RE.match(cleaned)
    if pb_match:
        result["project"] = pb_match.group(1)
        result["build"] = pb_match.group(2).upper()
        cleaned = cleaned[pb_match.end():].strip(" -_")

    # ── What remains is the CFG ──
    # Clean up any leftover separators, trailing "w" artifact (from "w HS")
    cfg = re.sub(r"\s+w$", "", cleaned, flags=re.IGNORECASE).strip(" -_")
    cfg = re.sub(r"[_ ]+$", "", cfg).strip(" -_")
    result["cfg"] = cfg if cfg else name  # fallback to original name

    # ── Build display parts ──
    result["display_parts"] = _build_display_parts(result)

    return result


def _normalize_precondition(raw: str) -> str:
    """Normalize pre-condition string."""
    upper = raw.upper().replace(" ", "")
    if upper == "NONHS":
        return "NonHS"
    if "CORNER" in upper:
        return "4-Corner"
    return "HS"


def _build_display_parts(parsed: dict) -> list[str]:
    """Build ordered list of non-empty display segments."""
    parts = []

    # Project-Build combined
    proj_build = ""
    if parsed["project"] and parsed["build"]:
        proj_build = f"{parsed['project']}-{parsed['build']}"
    elif parsed["project"]:
        proj_build = parsed["project"]
    elif parsed["build"]:
        proj_build = parsed["build"]
    if proj_build:
        parts.append(proj_build)

    # CFG
    if parsed["cfg"]:
        parts.append(parsed["cfg"])

    # Pre-condition
    if parsed["precondition"]:
        parts.append(parsed["precondition"])

    # Checkpoint + Extra
    cp = parsed["checkpoint"]
    if cp:
        if parsed["extra"]:
            cp = f"{cp} {parsed['extra']}"
        parts.append(cp)
    elif parsed["extra"]:
        parts.append(parsed["extra"])

    return parts
