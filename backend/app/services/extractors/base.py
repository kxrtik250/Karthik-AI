from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ExtractedPage:
    """Represents text extracted from a discrete page, slide, or section."""

    text: str
    page_number: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseExtractor(ABC):
    """Abstract interface for document text extractors."""

    @abstractmethod
    def extract(self, file_path: str) -> List[ExtractedPage]:
        """Extract pages/sections with text from the document."""
        pass
