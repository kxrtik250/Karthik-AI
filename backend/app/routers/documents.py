import uuid
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.document import Document, DocumentChunk
from app.schemas.document import DocumentChunkResponse, DocumentResponse
from app.services.ingestion_service import ingestion_service
from app.services.storage_service import MIME_TYPE_MAP, storage_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document (PDF, DOCX, PPTX, TXT, MD) up to 25 MB.
    Triggers asynchronous ingestion: extraction, chunking, embedding generation, and vector storage.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must have a filename.",
        )

    # 1. Validate file extension
    is_valid, file_type = storage_service.validate_file_type(file.filename)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type. Supported extensions: .pdf, .docx, .pptx, .txt, .md",
        )

    # 2. Save file & compute SHA-256 checksum
    try:
        saved_name, file_path, file_size, checksum = await storage_service.save_upload_file(file)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process and store uploaded file: {str(e)}",
        )

    # 3. Check duplicate checksum
    existing = await db.execute(select(Document).where(Document.checksum == checksum))
    duplicate = existing.scalars().first()
    if duplicate:
        # Clean up temporary disk file
        storage_service.delete_file(file_path)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": f"Duplicate file detected. File '{file.filename}' has identical checksum to '{duplicate.original_filename}'.",
                "existing_document_id": str(duplicate.id),
                "checksum": checksum,
            },
        )

    mime_type = file.content_type or MIME_TYPE_MAP.get(file_type, "application/octet-stream")

    # 4. Insert initial document record
    document = Document(
        filename=saved_name,
        original_filename=file.filename,
        file_type=file_type,
        mime_type=mime_type,
        file_size=file_size,
        file_path=file_path,
        checksum=checksum,
        status="processing",
    )
    db.add(document)
    await db.commit()
    await db.refresh(document)

    # 5. Dispatch background extraction, chunking, and embedding
    background_tasks.add_task(ingestion_service.process_document, document.id)

    return document


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (processing, completed, failed)"),
    db: AsyncSession = Depends(get_db),
):
    """List all uploaded documents."""
    query = select(Document).order_by(Document.created_at.desc())
    if status_filter:
        query = query.where(Document.status == status_filter)

    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve metadata, status, chunk counts, and error details for a document."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )
    return document


@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
async def get_document_chunks(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Retrieve chunk details (content, page/slide number, tokens) for debugging/inspection."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    chunks_result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index.asc())
    )
    return chunks_result.scalars().all()


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Delete a document, cascade delete its chunks, and delete the physical file."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalars().first()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found.",
        )

    file_path = document.file_path
    await db.delete(document)
    await db.commit()

    # Clean up physical file
    storage_service.delete_file(file_path)
    return None
