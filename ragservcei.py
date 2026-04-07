# src/service/rag_service.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from src.service.document_processor import DocumentProcessor
from src.service.embedding_service import EmbeddingService
from src.service.llm_service import LLMService


class RAGService:
    def __init__(
        self,
        document_processor: DocumentProcessor,
        llm_service: LLMService,
    ) -> None:
        self.document_processor = document_processor
        self.llm_service = llm_service

    async def ask(
        self,
        db: Session,
        project_id: int,
        question: str,
        top_k: int = 8,
        max_retries: int = 2,
        similarity_threshold: float = 0.45,
        include_debug_trace: bool = False,
    ) -> Dict[str, Any]:
        trace: List[Dict[str, Any]] = []
        rewritten_question: Optional[str] = None
        current_question = question
        retries_used = 0

        for attempt in range(max_retries + 1):
            trace.append({
                "step": "retrieve",
                "decision": "start",
                "details": {"attempt": attempt, "question": current_question},
            })

            retrieved = await self.document_processor.search_similar_chunks(
                query_text=current_question,
                project_id=project_id,
                db=db,
                limit=top_k,
            )

            retrieved = [
                r for r in retrieved
                if r.get("similarity_score", 0.0) >= similarity_threshold
            ]

            trace.append({
                "step": "retrieve",
                "decision": "completed",
                "details": {"retrieved_count": len(retrieved)},
            })

            # Grade documents
            filtered_docs: List[Dict[str, Any]] = []
            for doc in retrieved:
                grade = await self.llm_service.grade_retrieval_relevance(
                    question=current_question,
                    document=doc["text"],
                )
                if grade.lower() == "yes":
                    filtered_docs.append(doc)

            trace.append({
                "step": "grade_documents",
                "decision": "completed",
                "details": {
                    "input_docs": len(retrieved),
                    "relevant_docs": len(filtered_docs),
                },
            })

            if not filtered_docs:
                if attempt < max_retries:
                    new_question = await self.llm_service.rewrite_question(current_question)
                    rewritten_question = new_question
                    current_question = new_question
                    retries_used += 1
                    trace.append({
                        "step": "rewrite_question",
                        "decision": "retry",
                        "details": {"rewritten_question": current_question},
                    })
                    continue

                return {
                    "success": True,
                    "project_id": project_id,
                    "question": question,
                    "rewritten_question": rewritten_question,
                    "answer": "I could not find enough relevant evidence in the project documents to answer this reliably.",
                    "citations": [],
                    "grounded": False,
                    "useful": False,
                    "retries_used": retries_used,
                    "trace": trace if include_debug_trace else [],
                }

            answer = await self.llm_service.generate_rag_answer(
                question=current_question,
                chunks=filtered_docs,
            )

            trace.append({
                "step": "generate",
                "decision": "completed",
                "details": {"answer_length": len(answer)},
            })

            evidence_text = "\n\n".join(
                f"[Chunk {d['id']}] {d['text']}" for d in filtered_docs
            )

            grounded_grade = await self.llm_service.grade_grounding(
                question=current_question,
                answer=answer,
                documents=evidence_text,
            )
            grounded = grounded_grade.lower() == "yes"

            trace.append({
                "step": "grade_grounding",
                "decision": grounded_grade.lower(),
                "details": {},
            })

            useful_grade = await self.llm_service.grade_answer_usefulness(
                question=current_question,
                answer=answer,
            )
            useful = useful_grade.lower() == "yes"

            trace.append({
                "step": "grade_usefulness",
                "decision": useful_grade.lower(),
                "details": {},
            })

            if grounded and useful:
                citations = []
                for d in filtered_docs[:5]:
                    metadata = d.get("metadata", {})
                    citations.append({
                        "chunk_id": d["id"],
                        "filename": metadata.get("filename", "unknown"),
                        "file_hash": metadata.get("file_hash", "unknown"),
                        "chunk_index": metadata.get("chunk_index"),
                        "similarity_score": d.get("similarity_score", 0.0),
                        "excerpt": d["text"][:280],
                    })

                return {
                    "success": True,
                    "project_id": project_id,
                    "question": question,
                    "rewritten_question": rewritten_question,
                    "answer": answer,
                    "citations": citations,
                    "grounded": grounded,
                    "useful": useful,
                    "retries_used": retries_used,
                    "trace": trace if include_debug_trace else [],
                }

            if attempt < max_retries:
                current_question = await self.llm_service.rewrite_question(current_question)
                rewritten_question = current_question
                retries_used += 1
                trace.append({
                    "step": "rewrite_question",
                    "decision": "retry_after_generation",
                    "details": {"rewritten_question": current_question},
                })
                continue

            citations = []
            for d in filtered_docs[:5]:
                metadata = d.get("metadata", {})
                citations.append({
                    "chunk_id": d["id"],
                    "filename": metadata.get("filename", "unknown"),
                    "file_hash": metadata.get("file_hash", "unknown"),
                    "chunk_index": metadata.get("chunk_index"),
                    "similarity_score": d.get("similarity_score", 0.0),
                    "excerpt": d["text"][:280],
                })

            return {
                "success": True,
                "project_id": project_id,
                "question": question,
                "rewritten_question": rewritten_question,
                "answer": answer,
                "citations": citations,
                "grounded": grounded,
                "useful": useful,
                "retries_used": retries_used,
                "trace": trace if include_debug_trace else [],
            }
