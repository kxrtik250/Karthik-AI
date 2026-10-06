import uuid
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000, description="The user question to ask")
    top_k: Optional[int] = Field(None, ge=1, le=20, description="Max number of source chunks to retrieve")
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum cosine similarity")
    document_id: Optional[uuid.UUID] = Field(None, description="Optional document filter")


class SourceCitationResponse(BaseModel):
    source_index: int
    document_id: str
    filename: str
    page_number: Optional[int] = None
    chunk_index: int
    snippet: str
    similarity_score: float

    model_config = ConfigDict(from_attributes=True)


class RAGQueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceCitationResponse]
    model: str
    context_used: bool
    grounded: bool
