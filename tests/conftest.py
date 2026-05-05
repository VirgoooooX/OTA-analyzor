import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield Path(path)
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def temp_dirs():
    """Create temporary DATA_DIR, UPLOAD_DIR, and config dir."""
    base = Path(tempfile.mkdtemp())
    data_dir = base / "Raw Data"
    upload_dir = base / "uploads"
    config_dir = base / "config"
    data_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    yield {"base": base, "data": data_dir, "uploads": upload_dir, "config": config_dir}
    import shutil
    shutil.rmtree(base, ignore_errors=True)
