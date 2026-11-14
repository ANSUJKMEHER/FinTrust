import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.db.models.document import DocumentClassification, ProcessingStatus


class DocumentCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    original_filename: str = Field(..., min_length=1, max_length=500)
    mime_type: str = Field(..., min_length=1, max_length=100)
    file_size_bytes: int = Field(..., gt=0)
    content_hash: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash")
    classification: DocumentClassification = Field(default=DocumentClassification.INTERNAL)
    category: str = Field(default="GENERAL_COMPLIANCE", min_length=1, max_length=100)
    storage_path: str = Field(..., min_length=1, max_length=1000)
    total_pages: Optional[int] = Field(None, ge=1)


class DocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    classification: Optional[DocumentClassification] = None
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    status: Optional[ProcessingStatus] = None
    error_message: Optional[str] = None


class DocumentVersionResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version_num: int
    storage_path: str
    total_pages: Optional[int]
    total_chunks: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    title: str
    original_filename: str
    mime_type: str
    file_size_bytes: int
    content_hash: str
    classification: DocumentClassification
    category: str
    current_version_num: int
    status: ProcessingStatus
    error_message: Optional[str]
    created_by_id: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentResponse):
    versions: List[DocumentVersionResponse] = []


class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    title: str
    status: ProcessingStatus
    error_message: Optional[str] = None
    current_version_num: int
    total_versions: int
    total_chunks: int

    model_config = {"from_attributes": True}
