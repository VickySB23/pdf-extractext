import io
import hashlib
from dataclasses import dataclass
from pypdf import PdfReader

# Importamos nuestro logger
from app.core.logger import logger

@dataclass
class ExtractedPDF:
    filename: str
    text: str
    checksum: str

class PDFService:
    def extract_text(self, file_content: bytes, filename: str) -> ExtractedPDF:
        logger.info(f"Iniciando extracción de texto para el archivo: '{filename}'")
        
        try:
            pdf_stream = io.BytesIO(file_content)
            reader = PdfReader(pdf_stream)
            
            pages_text = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
                    
            clean_text = "\n".join(pages_text).strip()
        
            if not clean_text:
                logger.warning(f"El archivo '{filename}' se procesó, pero no se encontró texto (posible PDF escaneado).")
            else:
                logger.info(f"Texto extraído exitosamente de '{filename}' ({len(reader.pages)} páginas procesadas).")
                
            checksum = hashlib.sha256(clean_text.encode('utf-8')).hexdigest()
            
            return ExtractedPDF(
                filename=filename,
                text=clean_text,
                checksum=checksum
            )
            
        except Exception as e:
            logger.error(f"Error crítico al leer el PDF '{filename}': {str(e)}")
            raise ValueError(f"No se pudo procesar el archivo PDF. Puede estar dañado o protegido.")