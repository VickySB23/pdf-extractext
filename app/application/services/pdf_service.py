"""PDF text extraction service."""

import io
from dataclasses import dataclass
from pypdf import PdfReader
import hashlib
from io import BytesIO


@dataclass
class ExtractedPDF:
    filename: str
    text: str
    page_count: int
    character_count: int
    checksum: str


class PDFService:
    def extract_text(self, file_content: bytes, filename: str) -> ExtractedPDF:
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        reader = PdfReader(io.BytesIO(file_content))
        text_parts = []

        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

        full_text = "\n\n".join(text_parts)

        return ExtractedPDF(
            filename=filename,
            text=full_text,
            page_count=len(reader.pages),
            character_count=len(full_text),
            checksum=file_hash,
        )
