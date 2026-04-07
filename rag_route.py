# src/api/rag_routes.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.db import get_db
from src.service.embedding_service import EmbeddingService
from src.service.document_processor import DocumentProcessor
from src.service.llm_service import LLMService
from src.service.rag_service import RAGService
from src.api.rag_schemas import RAGAskRequest, RAGAskResponse

router = APIRouter()

embedding_service = EmbeddingService()
document_processor = DocumentProcessor(embedding_service)
llm_service = LLMService()
rag_service = RAGService(document_processor=document_processor, llm_service=llm_service)

@router.post("/rag/ask", response_model=RAGAskResponse)
async def ask_rag(
    request: RAGAskRequest,
    db: Session = Depends(get_db),
) -> RAGAskResponse:
    try:
        result = await rag_service.ask(
            db=db,
            project_id=request.project_id,
            question=request.question,
            top_k=request.top_k,
            max_retries=request.max_retries,
            similarity_threshold=request.similarity_threshold,
            include_debug_trace=request.include_debug_trace,
        )
        return RAGAskResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG ask failed: {str(e)}")
