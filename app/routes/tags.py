from fastapi import APIRouter, HTTPException

from app.models import UpdateTagsRequest
from app.services.tag_service import update_file_tags

router = APIRouter(prefix="/api", tags=["tags"])


@router.post("/tags")
def api_update_file_tags(request: UpdateTagsRequest):
    try:
        update_file_tags(request.filename, request.tags)
        return {"status": "success"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
