import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
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
from app.db.session import get_db
from app.schemas.document import (
    DocumentCreate,
    DocumentDetailResponse,
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionResponse
)
from app.schemas.permission import PermissionGrant, PermissionResponse
from app.services.document_service import DocumentService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/documents", tags=["Documents"])


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
