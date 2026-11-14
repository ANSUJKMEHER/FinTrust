from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ParsedBlock:
    """Represents an atomic structural content block extracted from a document."""
    block_type: str  # 'heading', 'paragraph', 'table', 'code', 'list_item'
    content: str
    page_number: Optional[int] = None
    heading_level: Optional[int] = None  # 1 for H1, 2 for H2, etc.
    section_heading: Optional[str] = None
    heading_breadcrumb: Optional[str] = None  # e.g., 'Section 3 > AML > Reporting'
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ParsedDocument:
    """Container for parsed document elements, structural metadata, and warnings."""
    title: Optional[str] = None
    total_pages: Optional[int] = None
    blocks: List[ParsedBlock] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseParser(ABC):
    """Abstract base class for format-specific document parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> ParsedDocument:
        """Parses a document file and returns a structured ParsedDocument."""
        pass

    @abstractmethod
    def can_parse(self, file_path: Path, mime_type: Optional[str] = None) -> bool:
        """Determines if this parser handles the given file format."""
        pass
