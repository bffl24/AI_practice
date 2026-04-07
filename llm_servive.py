# src/service/llm_service.py
from pydantic import BaseModel, Field

class BinaryGrade(BaseModel):
    binary_score: str = Field(description="yes or no")

class AnswerWithReason(BaseModel):
    answer: str
    used_chunk_ids: list[int] = Field(default_factory=list)

async def grade_retrieval_relevance(self, question: str, document: str) -> str:
    system_prompt = """
    You are grading whether a retrieved document chunk is relevant to a user question.
    Return only yes or no.
    """
    user_prompt = f"Question:\n{question}\n\nDocument:\n{document}"
    # call gateway and parse structured output

async def grade_grounding(self, question: str, answer: str, documents: str) -> str:
    system_prompt = """
    You are grading whether an answer is fully grounded in the provided retrieved evidence.
    Return only yes or no.
    """

async def grade_answer_usefulness(self, question: str, answer: str) -> str:
    system_prompt = """
    You are grading whether the answer resolves the user's question.
    Return only yes or no.
    """

async def rewrite_question(self, question: str) -> str:
    system_prompt = """
    Rewrite the user's question to improve semantic retrieval while preserving intent.
    Return only the rewritten question.
    """

async def generate_rag_answer(self, question: str, chunks: list[dict]) -> str:
    # compose context from retrieved chunks and ask model to answer only from context
