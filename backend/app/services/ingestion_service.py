import uuid
from typing import List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.document import Document, DocumentChunk
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_provider
from app.services.extractors.factory import get_extractor


class IngestionService:
    """Orchestrates document extraction, chunking, embedding, and storage."""

    async def process_document(self, document_id: uuid.UUID) -> None:
        """
        Background task to process a document:
        1. Loads document record
        2. Extracts text
        3. Chunks content
        4. Computes embeddings
        5. Saves chunks and marks document as completed (or failed with error message)
        """
        async with async_session() as db:
            result = await db.execute(select(Document).where(Document.id == document_id))
            doc = result.scalars().first()
            if not doc:
                return

            try:
                # 1. Update status to processing
                doc.status = "processing"
                doc.error_message = None
                await db.commit()
                await db.refresh(doc)

                # 2. Extract text
                extractor = get_extractor(doc.file_type)
                pages = extractor.extract(doc.file_path)

                if not pages:
                    raise ValueError(
                        f"Document contains no extractable text. File may be empty or image-only."
                    )

                doc.total_pages = len(pages)

                # 3. Chunk text
                chunks = chunking_service.chunk_pages(pages)
                if not chunks:
                    raise ValueError("Failed to create any chunks from extracted text.")

                # 4. Generate embeddings
                contents = [c.content for c in chunks]
                embeddings = embedding_provider.embed_texts(contents)

                # 5. Insert DocumentChunk entities
                chunk_records: List[DocumentChunk] = []
                for chunk_item, emb in zip(chunks, embeddings):
                    chunk_records.append(
                        DocumentChunk(
                            document_id=doc.id,
                            chunk_index=chunk_item.chunk_index,
                            content=chunk_item.content,
                            page_number=chunk_item.page_number,
                            token_count=chunk_item.token_count,
                            chunk_metadata=chunk_item.metadata,
                            embedding=emb,
                        )
                    )

                db.add_all(chunk_records)
                doc.total_chunks = len(chunk_records)
                doc.status = "completed"
                doc.error_message = None

                await db.commit()

            except Exception as e:
                await db.rollback()
                # Refresh session and record failure
                async with async_session() as fail_db:
                    f_res = await fail_db.execute(select(Document).where(Document.id == document_id))
                    f_doc = f_res.scalars().first()
                    if f_doc:
                        f_doc.status = "failed"
                        f_doc.error_message = str(e)
                        await fail_db.commit()


ingestion_service = IngestionService()
