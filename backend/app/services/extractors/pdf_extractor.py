from typing import List
from pypdf import PdfReader

from app.services.extractors.base import BaseExtractor, ExtractedPage


class PDFExtractor(BaseExtractor):
    """Extracts text from PDF documents preserving page numbers."""

    def extract(self, file_path: str) -> List[ExtractedPage]:
        pages: List[ExtractedPage] = []
        try:
            reader = PdfReader(file_path)
            for idx, page in enumerate(reader.pages, start=1):
                extracted = page.extract_text() or ""
                cleaned = extracted.strip()
                if cleaned:
                    pages.append(
                        ExtractedPage(
                            text=cleaned,
                            page_number=idx,
                            metadata={"page": idx, "total_pages": len(reader.pages)},
                        )
                    )
        except Exception as e:
            raise ValueError(f"Failed to extract text from PDF: {str(e)}")

        return pages
