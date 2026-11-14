import logging
from pathlib import Path
from typing import List, Optional
import docx

from app.parsers.base import BaseParser, ParsedBlock, ParsedDocument

logger = logging.getLogger(__name__)


class DOCXParser(BaseParser):
    """Production DOCX parser utilizing python-docx for headings, tables, and paragraphs."""

    def can_parse(self, file_path: Path, mime_type: Optional[str] = None) -> bool:
        if mime_type and (
            mime_type.lower() == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            or mime_type.lower() == "application/msword"
        ):
            return True
        return file_path.suffix.lower() in [".docx", ".doc"]

    def parse(self, file_path: Path) -> ParsedDocument:
        parsed_doc = ParsedDocument(title=file_path.stem)
        breadcrumb_stack: List[str] = []
        current_heading: Optional[str] = None

        try:
            doc = docx.Document(str(file_path))
            core_props = doc.core_properties
            if core_props.title:
                parsed_doc.title = core_props.title

            for elem in doc.element.body:
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

                if tag == "p":
                    p = docx.text.paragraph.Paragraph(elem, doc)
                    text = p.text.strip()
                    if not text:
                        continue

                    style_name = (p.style.name if p.style else "").lower()

                    if "heading 1" in style_name:
                        current_heading = text
                        breadcrumb_stack = [current_heading]
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="heading",
                                content=text,
                                heading_level=1,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack),
                                metadata={"style": p.style.name}
                            )
                        )
                    elif "heading 2" in style_name:
                        current_heading = text
                        if len(breadcrumb_stack) > 1:
                            breadcrumb_stack = [breadcrumb_stack[0], current_heading]
                        else:
                            breadcrumb_stack.append(current_heading)
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="heading",
                                content=text,
                                heading_level=2,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack),
                                metadata={"style": p.style.name}
                            )
                        )
                    elif "heading 3" in style_name:
                        current_heading = text
                        if len(breadcrumb_stack) > 2:
                            breadcrumb_stack = breadcrumb_stack[:2] + [current_heading]
                        else:
                            breadcrumb_stack.append(current_heading)
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="heading",
                                content=text,
                                heading_level=3,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack),
                                metadata={"style": p.style.name}
                            )
                        )
                    elif "list" in style_name or "bullet" in style_name:
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="list_item",
                                content=text,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None,
                                metadata={"style": p.style.name}
                            )
                        )
                    else:
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="paragraph",
                                content=text,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None,
                                metadata={"style": p.style.name}
                            )
                        )

                elif tag == "tbl":
                    tbl = docx.table.Table(elem, doc)
                    if not tbl.rows:
                        continue

                    table_data = []
                    for row in tbl.rows:
                        row_data = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                        table_data.append(row_data)

                    if table_data:
                        headers = table_data[0]
                        col_count = len(headers)
                        md_lines = [
                            "| " + " | ".join(headers) + " |",
                            "| " + " | ".join(["---"] * col_count) + " |"
                        ]
                        for row_data in table_data[1:]:
                            while len(row_data) < col_count:
                                row_data.append("")
                            md_lines.append("| " + " | ".join(row_data[:col_count]) + " |")

                        table_md = "\n".join(md_lines)
                        parsed_doc.blocks.append(
                            ParsedBlock(
                                block_type="table",
                                content=table_md,
                                section_heading=current_heading,
                                heading_breadcrumb=" > ".join(breadcrumb_stack) if breadcrumb_stack else None,
                                metadata={"rows": len(table_data), "columns": col_count}
                            )
                        )

        except Exception as e:
            logger.error(f"Failed to parse DOCX file {file_path}: {e}")
            parsed_doc.warnings.append(f"DOCX parsing error: {e}")

        return parsed_doc
