import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.rag import SourceCitationResponse


class MessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    citations: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    messages: List[MessageResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationListResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RAGChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="User prompt or question")
    conversation_id: Optional[uuid.UUID] = Field(None, description="Existing conversation ID to continue")
    top_k: Optional[int] = Field(None, ge=1, le=20)
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)


class RAGChatResponse(BaseModel):
    conversation_id: uuid.UUID
    message: MessageResponse
    sources: List[SourceCitationResponse] = []
    model: str
