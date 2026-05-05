import os
import sys
from pathlib import Path


def get_resource_path(relative_path):
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)


if hasattr(sys, "_MEIPASS"):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "Raw Data"))
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "uploads"))
TAGS_FILE = Path(os.getenv("TAGS_FILE", BASE_DIR / "config" / "tags.json"))
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "config" / "ota.db"))
STATIC_DIR = get_resource_path("static")

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
PASSWORD = os.getenv("PASSWORD", "")
