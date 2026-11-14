import logging
from pathlib import Path
import re
from typing import List, Optional

from app.parsers.base import BaseParser, ParsedBlock, ParsedDocument

logger = logging.getLogger(__name__)


class TextMarkdownParser(BaseParser):
    """Production Text and Markdown parser preserving headings, lists, code blocks, and breadcrumbs."""

    HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$")
    LIST_REGEX = re.compile(r"^(\s*[-*+]|\s*\d+\.)\s+(.+)$")

    def can_parse(self, file_path: Path, mime_type: Optional[str] = None) -> bool:
        if mime_type:
            m = mime_type.lower()
            if m in ["text/plain", "text/markdown", "text/x-markdown", "application/octet-stream"]:
                return file_path.suffix.lower() in [".txt", ".md", ".markdown"]
        return file_path.suffix.lower() in [".txt", ".md", ".markdown"]

    def parse(self, file_path: Path) -> ParsedDocument:
        parsed_doc = ParsedDocument(title=file_path.stem)
        breadcrumb_stack: List[str] = []
        current_heading: Optional[str] = None

        try:
            # Read with UTF-8 encoding, fallback to latin-1
            content = ""
            for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            lines = content.splitlines()
            current_paragraph_lines: List[str] = []
            in_code_block = False
            code_block_lines: List[str] = []

            def flush_paragraph():
                nonlocal current_paragraph_lines
                if current_paragraph_lines:
                    text = "\n".join(current_paragraph_lines).strip()
                    if text:
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="paragraph",
                                content=text,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None
                            )
                        )
                    current_paragraph_lines = []

            for line in lines:
                stripped = line.strip()

                # Check code block fencing
                if stripped.startswith("```"):
                    if in_code_block:
                        code_block_lines.append(line)
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="code",
                                content="\n".join(code_block_lines),
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None
                            )
                        )
                        code_block_lines = []
                        in_code_block = False
                    else:
                        flush_paragraph()
                        in_code_block = True
                        code_block_lines.append(line)
                    continue

                if in_code_block:
                    code_block_lines.append(line)
                    continue

                # Empty line separates paragraphs
                if not stripped:
                    flush_paragraph()
                    continue

                # Check Markdown Heading
                heading_match = self.HEADING_REGEX.match(stripped)
                if heading_match:
                    flush_paragraph()
                    level = len(heading_match.group(1))
                    heading_text = heading_match.group(2).strip()
                    current_heading = heading_text

                    # Update breadcrumb stack
                    if level == 1:
                        breadcrumb_stack = [current_heading]
                    elif level == 2:
                        if len(breadcrumb_stack) >= 1:
                            breadcrumb_stack = [breadcrumb_stack[0], current_heading]
                        else:
                            breadcrumb_stack = [current_heading]
                    else:
                        if len(breadcrumb_stack) >= 2:
                            breadcrumb_stack = breadcrumb_stack[:2] + [current_heading]
                        else:
                            breadcrumb_stack.append(current_heading)

                    parsed_doc.blocks.append(
                        ParsedBlock(
                            block_type="heading",
                            content=heading_text,
                            heading_level=level,
                            section_heading=current_heading,
                            heading_breadcrumb=" > ".join(breadcrumb_stack)
                        )
                    )
                    continue

                # Check List Item
                list_match = self.LIST_REGEX.match(line)
                if list_match:
                    flush_paragraph()
                    parsed_doc.blocks.append(
                        ParsedBlock(
                            block_type="list_item",
                            content=stripped,
                            section_heading=current_heading,
                            heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None
                        )
                    )
                    continue

                # Accumulate paragraph text
                current_paragraph_lines.append(line)

            flush_paragraph()

            # Handle unclosed code block if present
            if code_block_lines:
                parsed_doc.blocks.append(
                    ParsedBlock(
                        block_type="code",
                        content="\n".join(code_block_lines),
                        section_heading=current_heading,
                        heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None
                    )
                )

        except Exception as e:
            logger.error(f"Failed to parse text/markdown file {file_path}: {e}")
            parsed_doc.warnings.append(f"Text parsing error: {e}")

        return parsed_doc
