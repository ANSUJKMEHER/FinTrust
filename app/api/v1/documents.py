from pathlib import Path
import uuid
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.exceptions import (
    DocumentAccessDeniedError,
    EntityAlreadyExistsError,
    EntityNotFoundError,
    PermissionDeniedError,
    TenantAccessViolationError
)
from app.db.models.document import DocumentClassification, ProcessingStatus
from app.db.models.user import User
from app.db.session import get_db, SessionLocal
from app.repositories.chunk_repository import ChunkRepository
from app.schemas.chunk import ChunkResponse
from app.schemas.document import (
    DocumentCreate,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentStatusResponse,
    DocumentUpdate,
    DocumentVersionResponse
)
from app.schemas.permission import PermissionGrant, PermissionResponse
from app.services.document_service import DocumentService
from app.services.file_validation_service import FileValidationError, FileValidationService
from app.services.ingestion_service import IngestionService
from app.services.permission_service import PermissionService
from app.services.storage_service import StorageService

router = APIRouter(prefix="/documents", tags=["Documents"])


def run_background_ingestion(document_id: uuid.UUID, version_id: uuid.UUID, file_path_str: str):
    """Executes asynchronous document ingestion in a dedicated database session."""
    with SessionLocal() as db:
        svc = IngestionService(db)
        svc.process_document(document_id, version_id, Path(file_path_str))


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    classification: DocumentClassification = Form(DocumentClassification.INTERNAL),
    category: str = Form("GENERAL_COMPLIANCE"),
    process_sync: bool = Form(False),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentResponse:
    """Uploads and ingests a document (PDF, DOCX, TXT, MD) with validation, hashing, and chunk indexing."""
    if not current_user.has_role("ADMIN") and not current_user.has_role("COMPLIANCE_OFFICER"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only ADMIN or COMPLIANCE_OFFICER roles can upload documents."
        )

    file_bytes = await file.read()
    try:
        sanitized_name, valid_mime, file_size, content_hash = FileValidationService.validate_file(
            file_bytes=file_bytes,
            filename=file.filename or "uploaded_document",
            content_type=file.content_type
        )
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    doc_service = DocumentService(db)
    storage = StorageService()

    # Save file to tenant-isolated storage
    ext = Path(sanitized_name).suffix
    saved_path = storage.save_file(
        tenant_id=current_user.tenant_id,
        content_hash=content_hash,
        extension=ext,
        file_bytes=file_bytes
    )

    doc_title = title.strip() if title and title.strip() else sanitized_name

    try:
        doc = doc_service.create_document(
            DocumentCreate(
                title=doc_title,
                original_filename=sanitized_name,
                mime_type=valid_mime,
                file_size_bytes=file_size,
                content_hash=content_hash,
                classification=classification,
                category=category,
                storage_path=str(saved_path)
            ),
            current_user
        )
    except EntityAlreadyExistsError as e:
        # Clean up saved file if duplicate
        storage.delete_file(str(saved_path))
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except Exception as e:
        storage.delete_file(str(saved_path))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create document: {e}")

    version_id = doc.versions[0].id if doc.versions else None
    if not version_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Document version missing.")

    if process_sync:
        ingestion = IngestionService(db)
        ingestion.process_document(doc.id, version_id, saved_path)
        db.refresh(doc)
    else:
        background_tasks.add_task(run_background_ingestion, doc.id, version_id, str(saved_path))

    return doc


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentStatusResponse:
    """Retrieves document processing status and chunk indexing count."""
    doc_service = DocumentService(db)
    try:
        doc = doc_service.get_document(document_id, current_user)
        total_chunks = sum(v.total_chunks for v in doc.versions)
        return DocumentStatusResponse(
            id=doc.id,
            title=doc.title,
            status=doc.status,
            error_message=doc.error_message,
            current_version_num=doc.current_version_num,
            total_versions=len(doc.versions),
            total_chunks=total_chunks
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DocumentAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{document_id}/reprocess", response_model=DocumentResponse)
def reprocess_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentResponse:
    """Reprocesses an existing document from stored file: re-parses, re-chunks, and re-indexes embeddings."""
    ingestion = IngestionService(db)
    try:
        return ingestion.reprocess_document(document_id, current_user)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{document_id}/chunks", response_model=List[ChunkResponse])
def list_document_chunks(
    document_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[ChunkResponse]:
    """Retrieves paginated chunks for an authorized document."""
    doc_service = DocumentService(db)
    try:
        # Enforces tenant isolation and document read permissions
        doc = doc_service.get_document(document_id, current_user)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DocumentAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    chunk_repo = ChunkRepository(db)
    chunks = chunk_repo.list_by_document(document_id, current_user.tenant_id, skip=skip, limit=limit)
    return chunks


@router.post("/", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(
    data: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentResponse:
    doc_service = DocumentService(db)
    try:
        doc = doc_service.create_document(data, current_user)
        return doc
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except EntityAlreadyExistsError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.get("/", response_model=List[DocumentResponse])
def list_documents(
    classification: Optional[DocumentClassification] = None,
    category: Optional[str] = None,
    status_filter: Optional[ProcessingStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[DocumentResponse]:
    doc_service = DocumentService(db)
    docs = doc_service.list_documents(
        user=current_user,
        classification=classification,
        category=category,
        status=status_filter,
        skip=skip,
        limit=limit
    )
    return docs


@router.get("/{document_id}", response_model=DocumentDetailResponse)
def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentDetailResponse:
    doc_service = DocumentService(db)
    try:
        doc = doc_service.get_document(document_id, current_user)
        versions_resp = [
            DocumentVersionResponse(
                id=v.id,
                document_id=v.document_id,
                version_num=v.version_num,
                storage_path=v.storage_path,
                total_pages=v.total_pages,
                total_chunks=v.total_chunks,
                created_at=v.created_at
            )
            for v in doc.versions
        ]
        return DocumentDetailResponse(
            id=doc.id,
            tenant_id=doc.tenant_id,
            title=doc.title,
            original_filename=doc.original_filename,
            mime_type=doc.mime_type,
            file_size_bytes=doc.file_size_bytes,
            content_hash=doc.content_hash,
            classification=doc.classification,
            category=doc.category,
            current_version_num=doc.current_version_num,
            status=doc.status,
            error_message=doc.error_message,
            created_by_id=doc.created_by_id,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            versions=versions_resp
        )
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DocumentAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/{document_id}", response_model=DocumentResponse)
def update_document(
    document_id: uuid.UUID,
    data: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentResponse:
    doc_service = DocumentService(db)
    try:
        return doc_service.update_document(document_id, data, current_user)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except DocumentAccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> None:
    doc_service = DocumentService(db)
    try:
        doc_service.delete_document(document_id, current_user)
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (DocumentAccessDeniedError, PermissionDeniedError) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/{document_id}/permissions", response_model=PermissionResponse, status_code=status.HTTP_201_CREATED)
def grant_permission(
    document_id: uuid.UUID,
    grant: PermissionGrant,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> PermissionResponse:
    perm_service = PermissionService(db)
    try:
        perm = perm_service.grant_permission(document_id, grant, current_user)
        return perm
    except EntityNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (PermissionDeniedError, TenantAccessViolationError) as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{document_id}/permissions", response_model=List[PermissionResponse])
def list_document_permissions(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[PermissionResponse]:
    perm_service = PermissionService(db)
    try:
        return perm_service.list_permissions(document_id, current_user)
    except PermissionDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
