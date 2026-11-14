from pathlib import Path
from typing import List, Optional

from app.core.exceptions import FinTrustBaseException
from app.parsers.base import BaseParser, ParsedBlock, ParsedDocument
from app.parsers.docx_parser import DOCXParser
from app.parsers.pdf_parser import PDFParser
from app.parsers.text_parser import TextMarkdownParser


class UnsupportedFormatError(FinTrustBaseException):
    """Raised when an uploaded file format does not match any registered parser."""
    pass


class ParserRegistry:
    """Registry managing available document parsers."""

    def __init__(self):
        self.parsers: List[BaseParser] = [
            PDFParser(),
            DOCXParser(),
            TextMarkdownParser(),
        ]

    def get_parser(self, file_path: Path, mime_type: Optional[str] = None) -> BaseParser:
        for parser in self.parsers:
            if parser.can_parse(file_path, mime_type):
                return parser
        raise UnsupportedFormatError(
            f"No registered parser available for file '{file_path.name}' with MIME '{mime_type}'."
        )


parser_registry = ParserRegistry()

__all__ = [
    "BaseParser",
    "ParsedBlock",
    "ParsedDocument",
    "PDFParser",
    "DOCXParser",
    "TextMarkdownParser",
    "ParserRegistry",
    "parser_registry",
    "UnsupportedFormatError"
]
