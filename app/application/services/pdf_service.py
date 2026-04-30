import io
import hashlib
from dataclasses import dataclass
from pypdf import PdfReader

@dataclass
class ExtractedPDF:
    filename: str
    text: str
    checksum: str

class PDFService:
    def extract_text(self, file_content: bytes, filename: str) -> ExtractedPDF:
        pdf_stream = io.BytesIO(file_content)
        reader = PdfReader(pdf_stream)
        
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
                
        clean_text = "\n".join(pages_text).strip()
        checksum = hashlib.sha256(clean_text.encode('utf-8')).hexdigest()
        
        return ExtractedPDF(
            filename=filename,
            text=clean_text,
            checksum=checksum
        )