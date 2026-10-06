import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session
from app.models.conversation import Conversation, Message
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import embedding_provider
from app.services.llm.base import ChatMessage
from app.services.llm.factory import get_llm_provider


@dataclass
class SourceCitation:
    source_index: int
    document_id: str
    filename: str
    page_number: Optional[int]
    chunk_index: int
    snippet: str
    similarity_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_index": self.source_index,
            "document_id": self.document_id,
            "filename": self.filename,
            "page_number": self.page_number,
            "chunk_index": self.chunk_index,
            "snippet": self.snippet,
            "similarity_score": round(self.similarity_score, 4),
        }


@dataclass
class RAGResponse:
    query: str
    answer: str
    sources: List[SourceCitation]
    model: str
    context_used: bool = True
    grounded: bool = True


GROUNDING_SYSTEM_PROMPT = """You are Karthik AI, a personal assistant.
Answer the user's question accurately, concisely, and factually, relying STRICTLY on the retrieved source passages provided below.

Grounding Rules:
1. Base your answer ONLY on the provided source passages.
2. If the provided context does not contain enough information to answer the question, state:
   "Based on your uploaded documents, there is not enough information to answer this question."
3. Cite sources using [Source 1], [Source 2], etc., corresponding to the sources provided.
4. Do not speculate or invent facts, qualifications, grades, dates, or details not present in the sources.
"""


class RAGService:
    def __init__(self):
        self.llm_provider = get_llm_provider()

    async def retrieve_relevant_chunks(
        self,
        db: AsyncSession,
        query: str,
        top_k: int = settings.rag_top_k,
        similarity_threshold: float = settings.rag_similarity_threshold,
        document_id: Optional[uuid.UUID] = None,
    ) -> List[SourceCitation]:
        """
        Embeds query and performs pgvector exact cosine similarity search.
        """
        # 1. Generate query embedding
        query_vectors = embedding_provider.embed_texts([query])
        if not query_vectors:
            return []
        query_vector = query_vectors[0]

        # 2. pgvector cosine distance: dc.embedding.cosine_distance(query_vector)
        # Cosine similarity = 1 - cosine_distance
        cosine_distance_col = DocumentChunk.embedding.cosine_distance(query_vector)

        stmt = (
            select(
                DocumentChunk,
                Document.original_filename,
                cosine_distance_col.label("distance"),
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == "completed")
        )

        if document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        # Ordering by distance ascending (closest first)
        stmt = stmt.order_by(cosine_distance_col.asc()).limit(top_k * 2)

        results = await db.execute(stmt)
        rows = results.all()

        citations: List[SourceCitation] = []
        source_idx = 1

        for chunk, orig_filename, distance in rows:
            similarity = 1.0 - float(distance) if distance is not None else 0.0
            if similarity < similarity_threshold:
                continue

            # Format snippet (max 300 chars for citation overview)
            snippet = chunk.content.strip()
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."

            citations.append(
                SourceCitation(
                    source_index=source_idx,
                    document_id=str(chunk.document_id),
                    filename=orig_filename,
                    page_number=chunk.page_number,
                    chunk_index=chunk.chunk_index,
                    snippet=snippet,
                    similarity_score=similarity,
                )
            )
            source_idx += 1
            if len(citations) >= top_k:
                break

        return citations

    def construct_context(self, sources: List[SourceCitation], full_chunks: List[str]) -> str:
        """Constructs a structured context block with [Source X] attribution tags."""
        context_parts = []
        for src, text in zip(sources, full_chunks):
            page_info = f", Page/Slide {src.page_number}" if src.page_number else ""
            context_parts.append(
                f"[Source {src.source_index}] (File: {src.filename}{page_info}):\n{text}"
            )
        return "\n\n".join(context_parts)

    async def query(
        self,
        db: AsyncSession,
        question: str,
        top_k: int = settings.rag_top_k,
        similarity_threshold: float = settings.rag_similarity_threshold,
        document_id: Optional[uuid.UUID] = None,
    ) -> RAGResponse:
        """
        Executes single-turn RAG retrieval and answer generation:
        1. Embeds question & retrieves top-k chunks above threshold
        2. If none found: returns insufficient information message
        3. Formats context with [Source X] tags
        4. Calls LLM with grounded system prompt
        5. Returns grounded answer + structured citations
        """
        sources = await self.retrieve_relevant_chunks(
            db=db,
            query=question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            document_id=document_id,
        )

        if not sources:
            return RAGResponse(
                query=question,
                answer="Based on your uploaded documents, there is not enough information to answer this question.",
                sources=[],
                model=self.llm_provider.model if hasattr(self.llm_provider, "model") else "none",
                context_used=False,
                grounded=True,
            )

        chunk_texts: List[str] = []
        for s in sources:
            res = await db.execute(
                select(DocumentChunk.content).where(
                    DocumentChunk.document_id == uuid.UUID(s.document_id),
                    DocumentChunk.chunk_index == s.chunk_index,
                )
            )
            text = res.scalars().first() or s.snippet
            chunk_texts.append(text)

        context_block = self.construct_context(sources, chunk_texts)
        prompt_with_context = f"Retrieved Document Context:\n{context_block}\n\nUser Question:\n{question}\n\nAnswer:"

        llm_resp = await self.llm_provider.generate(
            prompt=prompt_with_context,
            system_prompt=GROUNDING_SYSTEM_PROMPT,
        )

        return RAGResponse(
            query=question,
            answer=llm_resp.content,
            sources=sources,
            model=llm_resp.model,
            context_used=True,
            grounded=True,
        )

    async def chat(
        self,
        db: AsyncSession,
        message: str,
        conversation_id: Optional[uuid.UUID] = None,
        top_k: int = settings.rag_top_k,
        similarity_threshold: float = settings.rag_similarity_threshold,
    ) -> Dict[str, Any]:
        """
        Multi-turn conversational RAG:
        1. Resolves or creates conversation
        2. Builds standalone retrieval query from history if needed
        3. Retrieves relevant chunks & formats grounded context
        4. Injects context + dialogue history into LLM
        5. Persists both user and assistant messages with citations as JSONB
        """
        conversation = None
        history_messages: List[Message] = []

        if conversation_id:
            res = await db.execute(
                select(Conversation)
                .options(selectinload(Conversation.messages))
                .where(Conversation.id == conversation_id)
            )
            conversation = res.scalars().first()

        if not conversation:
            # Create new conversation with title based on first user message
            title = message[:50] + "..." if len(message) > 50 else message
            conversation = Conversation(title=title)
            db.add(conversation)
            await db.commit()
            await db.refresh(conversation)
        else:
            history_messages = conversation.messages

        # 1. Build search query (standalone query incorporating last user turn if follow-up)
        search_query = message
        if history_messages:
            last_user_msg = next((m.content for m in reversed(history_messages) if m.role == "user"), None)
            if last_user_msg and len(message.split()) < 6:
                # Short follow-up (e.g. "What about CGPA?", "Where is it located?")
                search_query = f"{last_user_msg} {message}"

        # 2. Retrieve sources
        sources = await self.retrieve_relevant_chunks(
            db=db,
            query=search_query,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        # 3. Save User Message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=message,
        )
        db.add(user_msg)
        await db.commit()

        # 4. Construct prompt and history
        chat_history: List[ChatMessage] = []
        for past in history_messages[-6:]:  # last 3 turns
            chat_history.append(ChatMessage(role=past.role, content=past.content))

        if sources:
            chunk_texts: List[str] = []
            for s in sources:
                res = await db.execute(
                    select(DocumentChunk.content).where(
                        DocumentChunk.document_id == uuid.UUID(s.document_id),
                        DocumentChunk.chunk_index == s.chunk_index,
                    )
                )
                text = res.scalars().first() or s.snippet
                chunk_texts.append(text)

            context_block = self.construct_context(sources, chunk_texts)
            prompt_with_context = f"Retrieved Document Context:\n{context_block}\n\nUser Question:\n{message}\n\nAnswer:"
        else:
            prompt_with_context = (
                f"No relevant document context found.\nUser Question:\n{message}\n\n"
                "State clearly that the uploaded documents do not contain information to answer this."
            )

        # 5. Call LLM
        llm_resp = await self.llm_provider.generate(
            prompt=prompt_with_context,
            system_prompt=GROUNDING_SYSTEM_PROMPT,
            history=chat_history,
        )

        # 6. Save Assistant Message with JSONB citations
        citations_json = [s.to_dict() for s in sources]
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=llm_resp.content,
            citations=citations_json,
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        return {
            "conversation_id": conversation.id,
            "message": assistant_msg,
            "sources": sources,
            "model": llm_resp.model,
        }


rag_service = RAGService()
