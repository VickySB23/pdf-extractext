from unittest.mock import patch, MagicMock
from app.application.services.pdf_service import PDFService

def test_extract_text_in_memory():
    pdf_service = PDFService()
    dummy_bytes = b"contenido falso de pdf en bytes"
    test_filename = "documento_prueba.pdf"

    with patch("app.application.services.pdf_service.PdfReader") as MockReader:
        
        mock_page_1 = MagicMock()
        mock_page_1.extract_text.return_value = "Hola, esto es la página 1."
        
        mock_page_2 = MagicMock()
        mock_page_2.extract_text.return_value = "Y esto es la página 2."
        
        mock_instance = MockReader.return_value
        mock_instance.pages = [mock_page_1, mock_page_2]

        result = pdf_service.extract_text(dummy_bytes, test_filename)
        
        assert result.filename == test_filename
        assert result.page_count == 2
        assert "página 1" in result.text
        assert "página 2" in result.text
        assert result.character_count == len(result.text)