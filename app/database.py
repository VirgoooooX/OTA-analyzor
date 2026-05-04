import json
import sqlite3
import threading

from app.config import DB_PATH, TAGS_FILE

_local = threading.local()

DDL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    tags_json TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS file_cache (
    file_path TEXT NOT NULL UNIQUE,
    mtime REAL NOT NULL,
    row_count INTEGER,
    sn_count INTEGER,
    channels TEXT NOT NULL DEFAULT '[]',
    frequencies TEXT NOT NULL DEFAULT '[]',
    unique_cps TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS file_metadata (
    filename TEXT NOT NULL UNIQUE,
    project TEXT NOT NULL DEFAULT '',
    build TEXT NOT NULL DEFAULT '',
    cfg TEXT NOT NULL DEFAULT '',
    precondition TEXT NOT NULL DEFAULT '',
    checkpoint TEXT NOT NULL DEFAULT '',
    test_item TEXT NOT NULL DEFAULT '',
    extra TEXT NOT NULL DEFAULT '',
    display_parts TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH))
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    return db


def get_db():
    if not hasattr(_local, "db") or _local.db is None:
        _local.db = _connect()
    return _local.db


def init_db():
    db = get_db()
    cur = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
    )
    if cur.fetchone() is None:
        # Fresh install
        db.executescript(DDL)
        db.execute("INSERT INTO schema_version (version) VALUES (2)")

        # Migrate from tags.json if it exists
        if TAGS_FILE.is_file():
            try:
                with open(TAGS_FILE, "r", encoding="utf-8") as f:
                    legacy_tags = json.load(f)
                count = 0
                for filename, tag_list in legacy_tags.items():
                    db.execute(
                        "INSERT OR REPLACE INTO tags (filename, tags_json) VALUES (?, ?)",
                        (filename, json.dumps(tag_list, ensure_ascii=False)),
                    )
                    count += 1
                print(f"Migrated {count} tag entries from {TAGS_FILE}")
            except Exception as e:
                print(f"Failed to migrate tags.json: {e}")

        db.commit()
        return

    # Schema migration
    row = db.execute("SELECT version FROM schema_version").fetchone()
    current_version = row["version"] if row else 1

    if current_version < 2:
        db.execute("""
            CREATE TABLE IF NOT EXISTS file_metadata (
                filename TEXT NOT NULL UNIQUE,
                project TEXT NOT NULL DEFAULT '',
                build TEXT NOT NULL DEFAULT '',
                cfg TEXT NOT NULL DEFAULT '',
                precondition TEXT NOT NULL DEFAULT '',
                checkpoint TEXT NOT NULL DEFAULT '',
                test_item TEXT NOT NULL DEFAULT '',
                extra TEXT NOT NULL DEFAULT '',
                display_parts TEXT NOT NULL DEFAULT '[]',
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        db.execute("UPDATE schema_version SET version = 2")
        print("Migrated database schema to version 2 (added file_metadata table)")
        db.commit()


# ── Tag CRUD ────────────────────────────────────────────


def get_all_tags() -> dict:
    db = get_db()
    rows = db.execute("SELECT filename, tags_json FROM tags").fetchall()
    return {row["filename"]: json.loads(row["tags_json"]) for row in rows}


def get_tags(filename: str) -> list:
    db = get_db()
    row = db.execute("SELECT tags_json FROM tags WHERE filename = ?", (filename,)).fetchone()
    if row:
        return json.loads(row["tags_json"])
    return []


def set_tags(filename: str, tags: list):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO tags (filename, tags_json, updated_at) "
        "VALUES (?, ?, datetime('now'))",
        (filename, json.dumps(tags, ensure_ascii=False)),
    )
    db.commit()


def get_all_tags_set() -> list:
    db = get_db()
    rows = db.execute("SELECT DISTINCT tags_json FROM tags").fetchall()
    tag_set = set()
    for row in rows:
        for tag in json.loads(row["tags_json"]):
            tag_set.add(tag)
    return sorted(tag_set)


# ── File Cache CRUD ─────────────────────────────────────


def get_file_cache(file_path: str, mtime: float) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT row_count, sn_count, channels, frequencies, unique_cps "
        "FROM file_cache WHERE file_path = ? AND mtime = ?",
        (file_path, mtime),
    ).fetchone()
    if row is None:
        return None
    return {
        "row_count": row["row_count"],
        "sn_count": row["sn_count"],
        "channels": json.loads(row["channels"]),
        "frequencies": json.loads(row["frequencies"]),
        "unique_cps": json.loads(row["unique_cps"]),
    }


def set_file_cache(file_path: str, mtime: float, metadata: dict):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO file_cache "
        "(file_path, mtime, row_count, sn_count, channels, frequencies, unique_cps, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (
            file_path,
            mtime,
            metadata.get("row_count"),
            metadata.get("sn_count"),
            json.dumps(metadata.get("channels", [])),
            json.dumps(metadata.get("frequencies", [])),
            json.dumps(metadata.get("unique_cps", [])),
        ),
    )
    db.commit()


# ── File Metadata CRUD ──────────────────────────────────


def get_file_metadata(filename: str) -> dict | None:
    db = get_db()
    row = db.execute(
        "SELECT project, build, cfg, precondition, checkpoint, test_item, extra, display_parts "
        "FROM file_metadata WHERE filename = ?",
        (filename,),
    ).fetchone()
    if row is None:
        return None
    return {
        "project": row["project"],
        "build": row["build"],
        "cfg": row["cfg"],
        "precondition": row["precondition"],
        "checkpoint": row["checkpoint"],
        "test_item": row["test_item"],
        "extra": row["extra"],
        "display_parts": json.loads(row["display_parts"]),
    }


def set_file_metadata(filename: str, parsed: dict):
    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO file_metadata "
        "(filename, project, build, cfg, precondition, checkpoint, test_item, extra, display_parts, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
        (
            filename,
            parsed.get("project", ""),
            parsed.get("build", ""),
            parsed.get("cfg", ""),
            parsed.get("precondition", ""),
            parsed.get("checkpoint", ""),
            parsed.get("test_item", ""),
            parsed.get("extra", ""),
            json.dumps(parsed.get("display_parts", []), ensure_ascii=False),
        ),
    )
    db.commit()
