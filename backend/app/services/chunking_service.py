import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.extractors.base import ExtractedPage


@dataclass
class ChunkItem:
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    token_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class ChunkingService:
    def __init__(self, target_chunk_size: int = 500, overlap: int = 50):
        self.target_chunk_size = target_chunk_size
        self.overlap = overlap

    def chunk_pages(self, pages: List[ExtractedPage]) -> List[ChunkItem]:
        """
        Chunks extracted pages while strictly preserving source page/slide numbers.
        """
        chunks: List[ChunkItem] = []
        global_index = 0

        for page in pages:
            text = page.text.strip()
            if not text:
                continue

            # If the page text fits comfortably in one chunk
            if len(text) <= self.target_chunk_size:
                chunks.append(
                    ChunkItem(
                        chunk_index=global_index,
                        content=text,
                        page_number=page.page_number,
                        token_count=max(1, len(text) // 4),
                        metadata={**page.metadata, "sub_chunk": 0},
                    )
                )
                global_index += 1
                continue

            # Otherwise, split by paragraphs/sentences with overlap
            page_chunks = self._split_text_with_overlap(text)
            for sub_idx, sub_text in enumerate(page_chunks):
                chunks.append(
                    ChunkItem(
                        chunk_index=global_index,
                        content=sub_text,
                        page_number=page.page_number,
                        token_count=max(1, len(sub_text) // 4),
                        metadata={**page.metadata, "sub_chunk": sub_idx},
                    )
                )
                global_index += 1

        return chunks

    def _split_text_with_overlap(self, text: str) -> List[str]:
        """Sliding window chunking with sentence/paragraph boundary preference."""
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        result: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            if not current_chunk:
                current_chunk = para
            elif len(current_chunk) + len(para) + 2 <= self.target_chunk_size:
                current_chunk += "\n\n" + para
            else:
                result.append(current_chunk)
                # Keep overlap if paragraph is long
                if len(para) > self.target_chunk_size:
                    # Break long paragraph
                    for i in range(0, len(para), self.target_chunk_size - self.overlap):
                        slice_text = para[i : i + self.target_chunk_size].strip()
                        if slice_text:
                            result.append(slice_text)
                    current_chunk = ""
                else:
                    current_chunk = para

        if current_chunk:
            result.append(current_chunk)

        return result


chunking_service = ChunkingService()
