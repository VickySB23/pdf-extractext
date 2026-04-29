import io
import hashlib
from dataclasses import dataclass
from pypdf import PdfReader

@dataclass
class ExtractedPDF:
    filename: str
    text: str
    page_count: int
    character_count: int
    checksum: str

class PDFService:
    def extract_text(self, file_content: bytes, filename: str) -> ExtractedPDF:
        pdf_stream = io.BytesIO(file_content)
        reader = PdfReader(pdf_stream)
        
        extracted_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"
                
        clean_text = extracted_text.strip()
        checksum = hashlib.sha256(clean_text.encode('utf-8')).hexdigest()
        
        return ExtractedPDF(
            filename=filename,
            text=clean_text,
            page_count=len(reader.pages),
            character_count=len(clean_text),
            checksum=checksum
        )