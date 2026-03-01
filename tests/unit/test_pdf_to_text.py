"""Tests for elsian.convert.pdf_to_text."""

from elsian.convert.pdf_to_text import extract_pdf_text, extract_pdf_text_from_file


class TestExtractPdfText:
    """Tests for PDF text extraction functions."""

    def test_invalid_bytes(self):
        """Non-PDF bytes should return empty string."""
        result = extract_pdf_text(b"this is not a pdf")
        assert result == ""

    def test_empty_bytes(self):
        result = extract_pdf_text(b"")
        assert result == ""

    def test_from_file_nonexistent(self):
        result = extract_pdf_text_from_file("/nonexistent/path/file.pdf")
        assert result == ""