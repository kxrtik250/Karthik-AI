# Document Ingestion & Storage Pipeline — Karthik AI

Phase 3 introduces the document ingestion and vector storage pipeline for personal document semantic search and future RAG.

---

## 1. Supported Document Formats

| Format | Extension | Extractor | Preservation |
|---|---|---|---|
| PDF | `.pdf` | `pypdf` | Page numbers, multi-page flows |
| Word Document | `.docx` | `python-docx` | Paragraphs, tables |
| PowerPoint | `.pptx` | `python-pptx` | Slide numbers, text frames |
| Plain Text | `.txt` | UTF-8 Stream | Plain formatting |
| Markdown | `.md` | UTF-8 Stream | Headings and formatting |

---

## 2. Ingestion Flow

1. **File Upload & Validation**:
   - Limit: Configurable via `MAX_FILE_SIZE_MB` (default: 25 MB).
   - Validates file extensions against whitelist.
2. **Checksum & Deduplication**:
   - Calculates streaming **SHA-256** checksum.
   - Prevents duplicate file uploads (`HTTP 409 Conflict`).
3. **Storage**:
   - Saves file to disk under `uploads/documents/{uuid}.{ext}`.
4. **Extraction**:
   - Modular extractor decomposes document into pages/slides while keeping structural line counts and metadata.
5. **Page-Aware Chunking**:
   - Splits document using a sliding character window (500 characters, 50 character overlap).
   - Maintains exact `page_number` or `slide_number` per chunk.
6. **Local Fast Embeddings**:
   - Uses `fastembed` with model `BAAI/bge-small-en-v1.5`.
   - Dimension: **384** (validated dynamically at startup).
   - Pure local CPU execution (ONNX Runtime) — zero external API keys, zero token fees, complete privacy.
7. **pgvector Storage**:
   - Chunks and embedding vectors are persisted into PostgreSQL `document_chunks` table with `CASCADE` deletion.
   - Document state transitions reliably to `completed` or `failed`.

---

## 3. API Endpoints

- `POST /api/documents/upload`: Upload file (`multipart/form-data`)
- `GET /api/documents`: List uploaded documents
- `GET /api/documents/{id}`: View document details and ingestion status
- `GET /api/documents/{id}/chunks`: Inspect chunks and metadata for debugging
- `DELETE /api/documents/{id}`: Delete document, chunks, and disk file
