import pytest
import tempfile
import os
from unittest.mock import Mock, patch

from src.Testaiownik.RAG.file_processor import (
    extract_text_from_pdf,
    extract_text_from_txt,
    extract_text_from_pptx,
    extract_text_from_docx,
)


class TestFileProcessor:

    def test_extract_text_from_txt_success(self):
        """Test successful text extraction from TXT file."""
        test_content = "This is a test text file.\nWith multiple lines."

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            result = extract_text_from_txt(temp_path)
            assert result == test_content
        finally:
            os.unlink(temp_path)

    def test_extract_text_from_txt_file_not_found(self):
        """Test TXT extraction with non-existent file."""
        result = extract_text_from_txt("non_existent_file.txt")
        assert result == ""

    def test_extract_text_from_txt_encoding_error(self):
        """Test TXT extraction with encoding issues."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".txt", delete=False) as f:
            f.write(b"\xff\xfe\x00\x00")  
            temp_path = f.name

        try:
            result = extract_text_from_txt(temp_path)
            assert result == ""
        finally:
            os.unlink(temp_path)

    @patch("src.Testaiownik.RAG.file_processor.pdfplumber")
    def test_extract_text_from_pdf_success(self, mock_pdfplumber):
        """Test successful PDF text extraction."""
        mock_page1 = Mock()
        mock_page1.extract_text.return_value = "Page 1 content\n"

        mock_page2 = Mock()
        mock_page2.extract_text.return_value = "Page 2 content\n"

        mock_pdf = Mock()
        mock_pdf.pages = [mock_page1, mock_page2]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        mock_pdfplumber.open.return_value = mock_pdf

        result = extract_text_from_pdf("test.pdf")

        assert result == [("Page 1 content\n", 1), ("Page 2 content\n", 2)]
        mock_pdfplumber.open.assert_called_once_with("test.pdf")

    @patch("src.Testaiownik.RAG.file_processor.pdfplumber")
    def test_extract_text_from_pdf_empty_pages(self, mock_pdfplumber):
        """Test PDF extraction with empty pages."""
        mock_page = Mock()
        mock_page.extract_text.return_value = None

        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__ = Mock(return_value=mock_pdf)
        mock_pdf.__exit__ = Mock(return_value=None)

        mock_pdfplumber.open.return_value = mock_pdf

        result = extract_text_from_pdf("test.pdf")

        assert result == []

    @patch("src.Testaiownik.RAG.file_processor.Document")
    def test_extract_text_from_docx_success(self, mock_document_class):
        """Test successful DOCX text extraction."""
        mock_para1 = Mock()
        mock_para1.text = "First paragraph"

        mock_para2 = Mock()
        mock_para2.text = "Second paragraph"

        mock_doc = Mock()
        mock_doc.paragraphs = [mock_para1, mock_para2]

        mock_document_class.return_value = mock_doc

        result = extract_text_from_docx("test.docx")

        assert result == "First paragraph\nSecond paragraph"
        mock_document_class.assert_called_once_with("test.docx")

    @patch("src.Testaiownik.RAG.file_processor.Document")
    def test_extract_text_from_docx_error(self, mock_document_class):
        """Test DOCX extraction with error."""
        mock_document_class.side_effect = Exception("File not found")

        result = extract_text_from_docx("test.docx")

        assert result == ""

    @patch("src.Testaiownik.RAG.file_processor.Presentation")
    def test_extract_text_from_pptx_success(self, mock_presentation_class):
        """Test successful PPTX text extraction."""
        mock_shape1 = Mock()
        mock_shape1.text = "Slide 1 text"

        mock_shape2 = Mock()
        mock_shape2.text = "Slide 1 more text"

        mock_shape3 = Mock(spec=[])  

        mock_slide1 = Mock()
        mock_slide1.shapes = [mock_shape1, mock_shape2, mock_shape3]

        mock_shape4 = Mock()
        mock_shape4.text = "Slide 2 text"

        mock_slide2 = Mock()
        mock_slide2.shapes = [mock_shape4]

        mock_presentation = Mock()
        mock_presentation.slides = [mock_slide1, mock_slide2]

        mock_presentation_class.return_value = mock_presentation

        result = extract_text_from_pptx("test.pptx")

        expected = [("Slide 1 text\nSlide 1 more text", 1), ("Slide 2 text", 2)]
        assert result == expected

    @patch("src.Testaiownik.RAG.file_processor.Presentation")
    def test_extract_text_from_pptx_error(self, mock_presentation_class):
        """Test PPTX extraction with error."""
        mock_presentation_class.side_effect = Exception("File corrupted")

        result = extract_text_from_pptx("test.pptx")

        assert result == []

    @patch("src.Testaiownik.RAG.file_processor.Presentation")
    def test_extract_text_from_pptx_empty_slides(self, mock_presentation_class):
        """Test PPTX extraction with empty slides."""
        mock_slide = Mock()
        mock_slide.shapes = []

        mock_presentation = Mock()
        mock_presentation.slides = [mock_slide]

        mock_presentation_class.return_value = mock_presentation

        result = extract_text_from_pptx("test.pptx")

        assert result == []


if __name__ == "__main__":
    pytest.main([__file__])
