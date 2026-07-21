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
    mock_reader_instance.is_encrypted = False
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

@patch('app.application.services.pdf_service.PdfReader')
def test_extract_text_raises_value_error_when_pdf_reader_fails(mock_pdf_reader_class, pdf_service):
    mock_pdf_reader_class.side_effect = Exception("invalid pdf")

    with pytest.raises(ValueError) as exc_info:
        pdf_service.extract_text(b"contenido invalido", "corrupto.pdf")

    assert "No se pudo procesar el archivo PDF" in str(exc_info.value)

@patch('app.application.services.pdf_service.hashlib.sha256')
@patch('app.application.services.pdf_service.PdfReader')
def test_extract_text_raises_specific_value_error_when_pdf_is_encrypted(
    mock_pdf_reader_class,
    mock_sha256,
    pdf_service,
):
    mock_reader_instance = MagicMock()
    mock_reader_instance.is_encrypted = True
    mock_reader_instance.pages = [MagicMock()]
    mock_pdf_reader_class.return_value = mock_reader_instance

    with pytest.raises(ValueError) as exc_info:
        pdf_service.extract_text(b"%PDF-1.7 protegido", "protegido.pdf")

    assert "El PDF está protegido con contraseña" in str(exc_info.value)
    mock_reader_instance.pages[0].extract_text.assert_not_called()
    mock_sha256.assert_not_called()

@patch('app.application.services.pdf_service.hashlib.sha256')
@patch('app.application.services.pdf_service.PdfReader')
def test_extract_text_raises_value_error_when_pages_have_no_text(
    mock_pdf_reader_class,
    mock_sha256,
    pdf_service,
):
    mock_page_with_none = MagicMock()
    mock_page_with_none.extract_text.return_value = None

    mock_page_with_empty_text = MagicMock()
    mock_page_with_empty_text.extract_text.return_value = ""

    mock_reader_instance = MagicMock()
    mock_reader_instance.is_encrypted = False
    mock_reader_instance.pages = [mock_page_with_none, mock_page_with_empty_text]
    mock_pdf_reader_class.return_value = mock_reader_instance

    with pytest.raises(ValueError) as exc_info:
        pdf_service.extract_text(b"%PDF contenido sin texto", "escaneado.pdf")

    assert "No se encontró texto extraíble" in str(exc_info.value)
    mock_sha256.assert_not_called()
