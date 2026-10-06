from typing import Dict, Type
from app.services.extractors.base import BaseExtractor
from app.services.extractors.docx_extractor import DOCXExtractor
from app.services.extractors.pdf_extractor import PDFExtractor
from app.services.extractors.pptx_extractor import PPTXExtractor
from app.services.extractors.txt_extractor import TextExtractor

EXTRACTOR_REGISTRY: Dict[str, Type[BaseExtractor]] = {
    "pdf": PDFExtractor,
    "docx": DOCXExtractor,
    "pptx": PPTXExtractor,
    "txt": TextExtractor,
    "md": TextExtractor,
}


def get_extractor(file_type: str) -> BaseExtractor:
    """Returns an instantiated extractor for the given file type."""
    normalized = file_type.lower().strip()
    if normalized not in EXTRACTOR_REGISTRY:
        raise ValueError(f"No extractor available for file type: '{file_type}'")
    return EXTRACTOR_REGISTRY[normalized]()
