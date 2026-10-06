from typing import List

from app.services.extractors.base import BaseExtractor, ExtractedPage


class TextExtractor(BaseExtractor):
    """Extracts text from TXT and Markdown files."""

    def extract(self, file_path: str) -> List[ExtractedPage]:
        try:
            # Try utf-8 first, fallback to latin-1
            encodings = ["utf-8", "utf-8-sig", "latin-1"]
            content = None
            for enc in encodings:
                try:
                    with open(file_path, "r", encoding=enc) as f:
                        content = f.read().strip()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                raise ValueError("Could not decode text file with supported encodings.")

            if not content:
                return []

            return [
                ExtractedPage(
                    text=content,
                    page_number=1,
                    metadata={"characters_count": len(content)},
                )
            ]
        except Exception as e:
            raise ValueError(f"Failed to extract text from plain document: {str(e)}")
