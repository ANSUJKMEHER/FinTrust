import logging
from pathlib import Path
from typing import List, Optional
import pymupdf

from app.parsers.base import BaseParser, ParsedBlock, ParsedDocument

logger = logging.getLogger(__name__)


class PDFParser(BaseParser):
    """Production PDF parser utilizing PyMuPDF with heading detection, table extraction, and page tracking."""

    def can_parse(self, file_path: Path, mime_type: Optional[str] = None) -> bool:
        if mime_type and mime_type.lower() == "application/pdf":
            return True
        return file_path.suffix.lower() == ".pdf"

    def parse(self, file_path: Path) -> ParsedDocument:
        parsed_doc = ParsedDocument()
        breadcrumb_stack: List[str] = []
        current_heading: Optional[str] = None

        try:
            doc = pymupdf.open(str(file_path))
            parsed_doc.total_pages = len(doc)
            parsed_doc.title = doc.metadata.get("title") or file_path.stem
            parsed_doc.metadata = dict(doc.metadata)

            for page_idx, page in enumerate(doc):
                page_num = page_idx + 1

                # 1. Extract and preserve tables
                table_rects = []
                try:
                    tabs = page.find_tables()
                    for tab in tabs:
                        table_df = tab.extract()
                        if table_df and len(table_df) > 0:
                            # Format table as Markdown table
                            headers = [str(c or "").strip() for c in table_df[0]]
                            col_count = len(headers)
                            md_lines = [
                                "| " + " | ".join(headers) + " |",
                                "| " + " | ".join(["---"] * col_count) + " |"
                            ]
                            for row in table_df[1:]:
                                row_cells = [str(c or "").strip().replace("\n", " ") for c in row]
                                # Pad or trim to header length
                                while len(row_cells) < col_count:
                                    row_cells.append("")
                                md_lines.append("| " + " | ".join(row_cells[:col_count]) + " |")

                            table_md = "\n".join(md_lines)
                            parsed_doc.blocks.append(
                                ParsedBlock(
                                    block_type="table",
                                    content=table_md,
                                    page_number=page_num,
                                    section_heading=current_heading,
                                    heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None,
                                    metadata={"rows": len(table_df), "columns": col_count}
                                )
                            )
                            table_rects.append(tab.bbox)
                except Exception as table_err:
                    parsed_doc.warnings.append(f"Page {page_num}: Table extraction warning: {table_err}")

                # 2. Extract text blocks with layout and font awareness
                page_dict = page.get_text("dict")
                for block in page_dict.get("blocks", []):
                    # Skip image blocks (type 1)
                    if block.get("type") != 0:
                        continue

                    # Check if block overlaps with an extracted table
                    bbox = pymupdf.Rect(block.get("bbox", [0, 0, 0, 0]))
                    if any(bbox.intersects(t_bbox) for t_bbox in table_rects):
                        continue

                    block_text_lines = []
                    max_font_size = 0.0
                    is_bold = False

                    for line in block.get("lines", []):
                        line_text_parts = []
                        for span in line.get("spans", []):
                            span_text = span.get("text", "")
                            if span_text.strip():
                                line_text_parts.append(span_text)
                                font_size = span.get("size", 0.0)
                                if font_size > max_font_size:
                                    max_font_size = font_size
                                flags = span.get("flags", 0)
                                if flags & (1 << 4):  # Bold flag in PyMuPDF
                                    is_bold = True
                        if line_text_parts:
                            block_text_lines.append(" ".join(line_text_parts))

                    block_content = "\n".join(block_text_lines).strip()
                    if not block_content:
                        continue

                    # Heading heuristics: larger font or bold with short text
                    is_heading = (max_font_size >= 13.0 or (is_bold and len(block_content) < 120)) and len(block_content) < 200

                    if is_heading:
                        current_heading = block_content
                        # Simple hierarchy estimation
                        if max_font_size >= 16.0:
                            breadcrumb_stack = [current_heading]
                            heading_level = 1
                        elif max_font_size >= 13.0:
                            if len(breadcrumb_stack) > 1:
                                breadcrumb_stack = [breadcrumb_stack[0], current_heading]
                            else:
                                breadcrumb_stack.append(current_heading)
                            heading_level = 2
                        else:
                            if len(breadcrumb_stack) > 2:
                                breadcrumb_stack = breadcrumb_stack[:2] + [current_heading]
                            else:
                                breadcrumb_stack.append(current_heading)
                            heading_level = 3

                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="heading",
                                content=block_content,
                                page_number=page_num,
                                heading_level=heading_level,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack),
                                metadata={"font_size": max_font_size, "is_bold": is_bold}
                            )
                        )
                    else:
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="paragraph",
                                content=block_content,
                                page_number=page_num,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None,
                                metadata={"font_size": max_font_size}
                            )
                        )

            doc.close()
        except Exception as e:
            logger.error(f"Failed to parse PDF file {file_path}: {e}")
            parsed_doc.warnings.append(f"PDF parsing error: {e}")

        return parsed_doc
