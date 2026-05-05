import json
import os

import pytest

import app.database as db_mod


def test_init_db_creates_tables(temp_db_path):
    # Override DB_PATH
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = temp_db_path
    try:
        # Reset thread-local so we get a fresh connection
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None

        db_mod.init_db()
        db = db_mod.get_db()
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "schema_version" in table_names
        assert "tags" in table_names
        assert "file_cache" in table_names
    finally:
        db_mod.DB_PATH = orig
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_init_db_idempotent(temp_db_path):
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = temp_db_path
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        db_mod.init_db()
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        # Second call should not raise
        db_mod.init_db()
    finally:
        db_mod.DB_PATH = orig
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_set_and_get_tags(temp_db_path):
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = temp_db_path
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        db_mod.init_db()

        db_mod.set_tags("test.csv", ["EVT", "NonHS"])
        tags = db_mod.get_tags("test.csv")
        assert tags == ["EVT", "NonHS"]
    finally:
        db_mod.DB_PATH = orig
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_get_all_tags(temp_db_path):
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = temp_db_path
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        db_mod.init_db()

        db_mod.set_tags("a.csv", ["Tag1"])
        db_mod.set_tags("b.csv", ["Tag2", "Tag3"])

        all_tags = db_mod.get_all_tags()
        assert all_tags == {"a.csv": ["Tag1"], "b.csv": ["Tag2", "Tag3"]}
    finally:
        db_mod.DB_PATH = orig
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_get_all_tags_set(temp_db_path):
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = temp_db_path
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        db_mod.init_db()

        db_mod.set_tags("a.csv", ["A", "B"])
        db_mod.set_tags("b.csv", ["B", "C"])

        tag_set = db_mod.get_all_tags_set()
        assert tag_set == ["A", "B", "C"]
    finally:
        db_mod.DB_PATH = orig
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_file_cache_miss_and_hit(temp_db_path, temp_dirs):
    orig = db_mod.DB_PATH
    db_mod.DB_PATH = temp_db_path
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        db_mod.init_db()

        # No cache entry
        result = db_mod.get_file_cache("/nonexistent/path.csv", 12345.0)
        assert result is None

        # Set cache
        db_mod.set_file_cache("/test/file.csv", 100.0, {
            "row_count": 42, "sn_count": 5,
            "channels": ["Tx_LC"], "frequencies": ["2402"],
            "unique_cps": ["T0", "CP1"],
        })

        # Hit with matching mtime
        result = db_mod.get_file_cache("/test/file.csv", 100.0)
        assert result is not None
        assert result["row_count"] == 42
        assert result["sn_count"] == 5
        assert result["channels"] == ["Tx_LC"]

        # Miss with different mtime
        result = db_mod.get_file_cache("/test/file.csv", 200.0)
        assert result is None
    finally:
        db_mod.DB_PATH = orig
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_migrate_from_tags_json(temp_db_path, temp_dirs):
    """Test that init_db imports from existing tags.json."""
    tags_file = temp_dirs["config"] / "tags.json"
    tags_file.write_text(json.dumps({
        "Organized_test1.csv": ["EVT", "NonHS"],
        "Organized_test2.csv": ["DVT"],
    }), encoding="utf-8")

    orig_db = db_mod.DB_PATH
    orig_tags = db_mod.TAGS_FILE
    db_mod.DB_PATH = temp_db_path
    db_mod.TAGS_FILE = tags_file
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        db_mod.init_db()

        all_tags = db_mod.get_all_tags()
        assert "Organized_test1.csv" in all_tags
        assert all_tags["Organized_test1.csv"] == ["EVT", "NonHS"]
        assert all_tags["Organized_test2.csv"] == ["DVT"]

        # tags.json should still exist (not deleted)
        assert tags_file.exists()
    finally:
        db_mod.DB_PATH = orig_db
        db_mod.TAGS_FILE = orig_tags
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_migrate_handles_missing_tags_json(temp_db_path):
    """Test that init_db doesn't fail when tags.json is missing."""
    orig_db = db_mod.DB_PATH
    orig_tags = db_mod.TAGS_FILE
    db_mod.DB_PATH = temp_db_path
    db_mod.TAGS_FILE = temp_db_path.parent / "nonexistent_tags.json"
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        # Should not raise
        db_mod.init_db()
        all_tags = db_mod.get_all_tags()
        assert all_tags == {}
    finally:
        db_mod.DB_PATH = orig_db
        db_mod.TAGS_FILE = orig_tags
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None


def test_migrate_handles_tags_json_as_directory(temp_db_path, temp_dirs):
    """Docker sometimes creates tags.json as a directory. Should skip gracefully."""
    tags_dir = temp_dirs["config"] / "tags.json"
    tags_dir.mkdir(exist_ok=True)

    orig_db = db_mod.DB_PATH
    orig_tags = db_mod.TAGS_FILE
    db_mod.DB_PATH = temp_db_path
    db_mod.TAGS_FILE = tags_dir
    try:
        if hasattr(db_mod._local, "db"):
            db_mod._local.db = None
        # Should not raise
        db_mod.init_db()
        all_tags = db_mod.get_all_tags()
        assert all_tags == {}
    finally:
        db_mod.DB_PATH = orig_db
        db_mod.TAGS_FILE = orig_tags
        if hasattr(db_mod._local, "db") and db_mod._local.db:
            db_mod._local.db.close()
            db_mod._local.db = None
