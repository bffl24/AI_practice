"""
Service for LLM-based content extraction and summarization.
"""

import json
import logging
from typing import List, Dict, Any, Optional
import httpx
from src.config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for LLM-based content processing via LLM Gateway."""

    def __init__(self) -> None:
        """Initialize LLM service."""
        self.api_key = settings.LLM_GATEWAY_API_KEY
        self.base_url = settings.LLM_GATEWAY_BASE_URL
        self.model = settings.LLM_GATEWAY_CHAT_MODEL
        self.system_prompt = settings.LLM_GATEWAY_CHAT_MODEL_SYSTEM_PROMPT
        self.user_prompt_template = settings.LLM_GATEWAY_CHAT_MODEL_USER_PROMPT
        self.timeout = settings.LLM_GATEWAY_TIMEOUT_CHAT_MODEL
        self.max_retries = settings.LLM_GATEWAY_MAX_RETRIES_CHAT_MODEL

    def _normalize_binary(self, value: str) -> str:
        value = value.strip().lower()
        if "yes" in value:
            return "yes"
        if "no" in value:
            return "no"
        return "no"

    def _format_chunks(self, chunks: List[Dict[str, Any]], limit: int = 10) -> str:
        context_parts = []
        for i, chunk in enumerate(chunks[:limit], 1):
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            chunk_id = chunk.get("id", "unknown")
            context_parts.append(
                f"[Chunk {i} | id={chunk_id} | file={filename}]\n{text}\n"
            )
        return "\n".join(context_parts)
    
    async def extract_topic_content(
        self, chunks: List[Dict[str, Any]], topic: str
    ) -> str:
        """
        Extract content related to a specific topic from chunks.
        
        Args:
            chunks: List of chunk dictionaries with text and metadata
            topic: The topic to extract information about
            
        Returns:
            Extracted and summarized content related to the topic
        """
        # Prepare context from chunks
        context_parts = []
        for i, chunk in enumerate(chunks[:10], 1):  # Limit to top 10 chunks
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            filename = metadata.get("filename", "unknown")
            context_parts.append(
                f"[Chunk {i} from {filename}]\n{text}\n"
            )
        
        context = "\n".join(context_parts)
        
        # Use user prompt template from settings and substitute variables
        user_prompt = self.user_prompt_template.format(topic=topic, context=context)

        # Call LLM with prompts from settings
        try:
            extracted_content = await self._call_llm(self.system_prompt, user_prompt)
            return extracted_content
        except Exception as e:
            logger.error(f"Error extracting topic content: {e}")
            raise

        async def generate_rag_answer(self, question: str, chunks: List[Dict[str, Any]]) -> str:
        context = self._format_chunks(chunks, limit=8)
        system_prompt = """
        You are a grounded enterprise RAG assistant.
        Answer only using the provided evidence.
        If the evidence is insufficient, say so clearly.
        Do not invent facts.
        """
        user_prompt = f"Question:\n{question}\n\nEvidence:\n{context}"
        return await self._call_llm(system_prompt, user_prompt)

    async def grade_retrieval_relevance(self, question: str, document: str) -> str:
        system_prompt = """
        You are grading whether a retrieved document chunk is relevant to a user question.
        Return only 'yes' or 'no'.
        """
        user_prompt = f"Question:\n{question}\n\nDocument:\n{document}"
        result = await self._call_llm(system_prompt, user_prompt)
        return self._normalize_binary(result)

    async def grade_grounding(self, question: str, answer: str, documents: str) -> str:
        system_prompt = """
        You are grading whether the answer is fully grounded in the provided evidence.
        Return only 'yes' or 'no'.
        """
        user_prompt = f"Question:\n{question}\n\nEvidence:\n{documents}\n\nAnswer:\n{answer}"
        result = await self._call_llm(system_prompt, user_prompt)
        return self._normalize_binary(result)

    async def grade_answer_usefulness(self, question: str, answer: str) -> str:
        system_prompt = """
        You are grading whether the answer resolves the user's question.
        Return only 'yes' or 'no'.
        """
        user_prompt = f"Question:\n{question}\n\nAnswer:\n{answer}"
        result = await self._call_llm(system_prompt, user_prompt)
        return self._normalize_binary(result)

    async def rewrite_question(self, question: str) -> str:
        system_prompt = """
        Rewrite the question to improve semantic retrieval while preserving user intent.
        Return only the rewritten question.
        """
        user_prompt = f"Original question:\n{question}"
        return (await self._call_llm(system_prompt, user_prompt)).strip()

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        """
        Call LLM Gateway for chat completion using Portkey-compatible format.
        
        Args:
            system_prompt: System message
            user_prompt: User message
            
        Returns:
            LLM response text
        """
        # Use the same format as embeddings - Portkey uses standard OpenAI format
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "x-portkey-api-key": self.api_key,  # Portkey format
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    response.raise_for_status()

                    data = response.json()
                    content = data["choices"][0]["message"]["content"]

                    logger.info("Successfully called LLM for content extraction")
                    return content

            except httpx.HTTPStatusError as e:
                error_detail = ""
                try:
                    error_detail = f" - Response: {e.response.text}"
                except:
                    pass
                logger.error(
                    f"HTTP error calling LLM (attempt {attempt + 1}/{self.max_retries}): {e}{error_detail}"
                )
                logger.error(f"Request payload: model={self.model}")
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.error(
                    f"Error calling LLM (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt == self.max_retries - 1:
                    raise

        raise Exception("Failed to call LLM after all retries")



