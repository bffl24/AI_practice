# src/api/rag_schemas.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RAGAskRequest(BaseModel):
    project_id: int = Field(..., gt=0)
    question: str = Field(..., min_length=1)
    top_k: int = Field(8, ge=1, le=20)
    max_retries: int = Field(2, ge=0, le=5)
    similarity_threshold: float = Field(0.45, ge=0.0, le=1.0)
    include_debug_trace: bool = Field(False)


class RAGCitation(BaseModel):
    chunk_id: int
    filename: str
    file_hash: str
    chunk_index: Optional[int] = None
    similarity_score: float
    excerpt: str


class RAGTraceStep(BaseModel):
    step: str
    decision: str
    details: Dict[str, Any] = {}


class RAGAskResponse(BaseModel):
    success: bool = True
    project_id: int
    question: str
    rewritten_question: Optional[str] = None
    answer: str
    citations: List[RAGCitation]
    grounded: bool
    useful: bool
    retries_used: int
    trace: List[RAGTraceStep] = []
