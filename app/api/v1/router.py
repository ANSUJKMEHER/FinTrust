from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.users import router as users_router
from app.api.v1.documents import router as documents_router
from app.api.v1.search import router as search_router
from app.api.v1.audit import router as audit_router
from app.api.v1.rag import router as rag_router
from app.api.v1.intelligence import router as intelligence_router
from app.api.v1.llm import router as llm_router
from app.api.v1.agentic import router as agentic_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(tenants_router)
api_router.include_router(users_router)
api_router.include_router(documents_router)
api_router.include_router(search_router)
api_router.include_router(audit_router)
api_router.include_router(rag_router)
api_router.include_router(intelligence_router)
api_router.include_router(llm_router)
api_router.include_router(agentic_router)
