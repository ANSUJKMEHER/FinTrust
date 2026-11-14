from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, ConfigDict


class ChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    document_version_id: uuid.UUID
    chunk_index: int
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    heading_breadcrumb: Optional[str] = None
    content: str
    token_count: int
    content_hash: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
