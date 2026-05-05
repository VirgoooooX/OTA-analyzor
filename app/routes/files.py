import os
import shutil
import uuid
from pathlib import Path
from typing import List

from fastapi import APIRouter, File, HTTPException, UploadFile

from analysis import resolve_data_file
from app.config import DATA_DIR, UPLOAD_DIR
from app.database import delete_file_cache, delete_file_metadata, delete_tags, get_tags
from app.services.file_service import list_files as list_all_files
from app.utils import ensure_runtime_dirs, safe_filename, raw_data_filename, file_entry

router = APIRouter(prefix="/api", tags=["files"])


@router.get("/files")
def api_list_files():
    ensure_runtime_dirs(str(DATA_DIR), str(UPLOAD_DIR))
    return list_all_files()


@router.post("/upload")
async def api_upload_files(files: List[UploadFile] = File(...)):
    ensure_runtime_dirs(str(DATA_DIR), str(UPLOAD_DIR))
    uploaded = []

    for upload in files:
        original_name = safe_filename(upload.filename or "upload.csv")
        if not original_name.lower().endswith(".csv"):
            raise HTTPException(status_code=400, detail=f"{original_name} 不是 CSV 文件")

        target_name = f"{uuid.uuid4().hex[:8]}_{original_name}"
        target_path = Path(UPLOAD_DIR) / target_name
        with target_path.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)

        ref = resolve_data_file(f"upload:{target_name}", str(DATA_DIR), str(UPLOAD_DIR))
        uploaded.append(file_entry(ref, ["Uploaded"]))

    return {"uploaded": uploaded}


@router.post("/rawdata/upload")
async def api_upload_raw_data_files(files: List[UploadFile] = File(...)):
    ensure_runtime_dirs(str(DATA_DIR), str(UPLOAD_DIR))
    uploaded = []

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

        existing_tags = get_tags(original_name)
        ref = resolve_data_file(f"raw:{original_name}", str(DATA_DIR), str(UPLOAD_DIR))
        uploaded.append(file_entry(ref, existing_tags))

    return {"uploaded": uploaded}


@router.delete("/files/{filename}")
async def api_delete_file(filename: str):
    # 路径遍历防护
    target_path = (Path(DATA_DIR) / filename).resolve()
    data_dir_resolved = Path(DATA_DIR).resolve()
    if not str(target_path).startswith(str(data_dir_resolved)):
        raise HTTPException(status_code=400, detail="非法文件路径")

    # 只允许删除 raw data 文件（以 Organized_ 开头）
    if not filename.startswith("Organized_"):
        raise HTTPException(status_code=400, detail="仅支持删除 raw data 文件")

    if not target_path.exists():
        raise HTTPException(status_code=404, detail=f"文件 {filename} 不存在")
    os.unlink(target_path)

    delete_tags(filename)
    delete_file_cache(str(target_path))
    delete_file_metadata(filename)

    return {"ok": True, "deleted": filename}
