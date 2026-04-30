import pytest
import hashlib
from unittest.mock import patch, MagicMock
from app.application.services.pdf_service import PDFService

@pytest.fixture
def pdf_service():
    return PDFService()

@patch('app.application.services.pdf_service.PdfReader')
def test_extract_text_success(mock_pdf_reader_class, pdf_service):
    # 1. ARRANGE
    mock_page_1 = MagicMock()
    mock_page_1.extract_text.return_value = "Hola"
    
    mock_page_2 = MagicMock()
    mock_page_2.extract_text.return_value = "Mundo"
    
    mock_reader_instance = MagicMock()
    mock_reader_instance.pages = [mock_page_1, mock_page_2]
    
    mock_pdf_reader_class.return_value = mock_reader_instance
    
    fake_pdf_bytes = b"bytes falsos de un pdf"
    expected_text = "Hola\nMundo"
    expected_checksum = hashlib.sha256(expected_text.encode('utf-8')).hexdigest()
    
    # 2. ACT
    result = pdf_service.extract_text(fake_pdf_bytes, "documento.pdf")
    
    # 3. ASSERT
    # 3. ASSERT
    assert result.filename == "documento.pdf"
    assert result.text == expected_text
    assert result.checksum == expected_checksum
    
    mock_pdf_reader_class.assert_called_once()