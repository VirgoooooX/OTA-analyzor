from typing import List

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    files: List[str]
    includeFailData: bool = False
    channels: List[str] | None = None


class UpdateTagsRequest(BaseModel):
    filename: str
    tags: List[str]
