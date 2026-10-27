import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.conversation import Conversation
from app.schemas.conversation import (
    ConversationListResponse,
    ConversationResponse,
    MessageResponse,
    RAGChatRequest,
    RAGChatResponse,
)
from app.schemas.rag import RAGQueryRequest, RAGQueryResponse, SourceCitationResponse
from app.services.llm.factory import get_llm_provider
from app.services.rag_service import rag_service

router = APIRouter(prefix="/rag", tags=["rag"])


@router.get("/provider", response_model=Dict[str, Any])
async def get_provider_status():
    """Returns the current LLM provider configuration and health check."""
    provider = get_llm_provider()
    is_healthy = await provider.is_healthy()
    return {
        "provider": settings.llm_provider,
        "model": settings.ollama_model,
        "base_url": settings.ollama_base_url,
        "healthy": is_healthy,
    }


@router.post("/query", response_model=RAGQueryResponse)
async def query_rag(
    request: RAGQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Executes a single-turn RAG retrieval and answer generation:
    1. Embeds question using local 384-dim FastEmbed model
    2. Performs exact cosine similarity search in PostgreSQL via pgvector
    3. Filters out chunks below the similarity threshold
    4. Constructs structured context with [Source X] tags
    5. Calls configured LLM with grounding system prompt
    6. Returns grounded response with structured source citations
    """
    top_k = request.top_k or settings.rag_top_k
    similarity_threshold = (
        request.similarity_threshold
        if request.similarity_threshold is not None
        else settings.rag_similarity_threshold
    )

    try:
        rag_res = await rag_service.query(
            db=db,
            question=request.question,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
            document_id=request.document_id,
        )

        citation_responses = [
            SourceCitationResponse(
                source_index=s.source_index,
                document_id=s.document_id,
                filename=s.filename,
                page_number=s.page_number,
                chunk_index=s.chunk_index,
                snippet=s.snippet,
                similarity_score=s.similarity_score,
            )
            for s in rag_res.sources
        ]

        return RAGQueryResponse(
            query=rag_res.query,
            answer=rag_res.answer,
            sources=citation_responses,
            structured_sources=rag_res.structured_sources,
            model=rag_res.model,
            context_used=rag_res.context_used,
            grounded=rag_res.grounded,
            intent=rag_res.intent,
            sources_used=rag_res.sources_used,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG query execution failed: {str(e)}",
        )


@router.post("/chat", response_model=RAGChatResponse)
async def chat_rag(
    request: RAGChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Executes multi-turn conversational RAG:
    1. Incorporates dialogue history
    2. Builds standalone query for retrieval when needed
    3. Retrieves context from documents via pgvector
    4. Calls LLM with dialogue history and retrieved context
    5. Persists conversation and messages with JSONB citations
    """
    top_k = request.top_k or settings.rag_top_k
    similarity_threshold = (
        request.similarity_threshold
        if request.similarity_threshold is not None
        else settings.rag_similarity_threshold
    )

    try:
        chat_res = await rag_service.chat(
            db=db,
            message=request.message,
            conversation_id=request.conversation_id,
            top_k=top_k,
            similarity_threshold=similarity_threshold,
        )

        msg_entity = chat_res["message"]
        citation_responses = [
            SourceCitationResponse(
                source_index=s.source_index,
                document_id=s.document_id,
                filename=s.filename,
                page_number=s.page_number,
                chunk_index=s.chunk_index,
                snippet=s.snippet,
                similarity_score=s.similarity_score,
            )
            for s in chat_res["sources"]
        ]

        return RAGChatResponse(
            conversation_id=chat_res["conversation_id"],
            message=MessageResponse(
                id=msg_entity.id,
                role=msg_entity.role,
                content=msg_entity.content,
                citations=msg_entity.citations,
                created_at=msg_entity.created_at,
            ),
            sources=citation_responses,
            structured_sources=chat_res.get("structured_sources", []),
            model=chat_res["model"],
            intent=chat_res.get("intent"),
            sources_used=chat_res.get("sources_used", []),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Conversational RAG failed: {str(e)}",
        )


@router.get("/context-summary", response_model=Dict[str, Any])
async def get_context_summary(
    query: Optional[str] = Query(None, description="Optional diagnostic query to evaluate routing, guards, and context retrieval"),
    db: AsyncSession = Depends(get_db),
):
    """Overview of available structured personal memory in PostgreSQL and query diagnostics."""
    return await rag_service.evaluate_context_summary(db=db, query=query)


@router.get("/conversations", response_model=List[ConversationListResponse])
async def list_conversations(db: AsyncSession = Depends(get_db)):
    """List all saved conversation sessions."""
    result = await db.execute(
        select(Conversation).order_by(Conversation.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve full conversation history and messages."""
    result = await db.execute(
        select(Conversation)
        .options(selectinload(Conversation.messages))
        .where(Conversation.id == conversation_id)
    )
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )
    return conv


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a conversation thread and all its messages."""
    result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    conv = result.scalars().first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found.",
        )
    await db.delete(conv)
    await db.commit()
    return None
