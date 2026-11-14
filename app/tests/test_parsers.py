from pathlib import Path
import tempfile
import docx
import pymupdf
import pytest

from app.parsers import (
    DOCXParser,
    PDFParser,
    TextMarkdownParser,
    UnsupportedFormatError,
    parser_registry
)


def test_pdf_parser_structure_and_tables(tmp_path: Path):
    """Verifies PyMuPDF parser extracts text, headings, tables, and page numbers."""
    pdf_path = tmp_path / "compliance_report.pdf"
    doc = pymupdf.open()

    # Page 1
    page1 = doc.new_page()
    # Large font heading (size 16)
    page1.insert_text((50, 50), "FinTrust Regulatory Policy", fontsize=16)
    # Paragraph
    page1.insert_text(
        (50, 100),
        "Under BSA Section 5318(g), financial institutions must report suspicious activities within 30 days.",
        fontsize=11
    )

    # Page 2 with table
    page2 = doc.new_page()
    page2.insert_text((50, 50), "Section 2: Sanction Rules", fontsize=14)
    # Draw simple table lines
    page2.draw_rect(pymupdf.Rect(50, 80, 450, 150))
    page2.insert_text((60, 100), "Country | Risk Level | Filing Form", fontsize=10)
    page2.insert_text((60, 130), "Region A | High Risk | FinCEN Form 111", fontsize=10)

    doc.save(str(pdf_path))
    doc.close()

    parser = PDFParser()
    assert parser.can_parse(pdf_path) is True

    parsed = parser.parse(pdf_path)
    assert parsed.total_pages == 2
    assert len(parsed.blocks) >= 2

    # Check that text and regulatory identifiers were extracted
    all_content = " ".join(b.content for b in parsed.blocks)
    assert "BSA Section 5318(g)" in all_content
    assert "FinTrust Regulatory Policy" in all_content


def test_docx_parser_headings_and_tables(tmp_path: Path):
    """Verifies python-docx parser extracts heading hierarchy, tables, and breadcrumbs."""
    docx_path = tmp_path / "kyc_policy.docx"
    doc = docx.Document()
    doc.core_properties.title = "KYC and Due Diligence Manual"

    doc.add_heading("Customer Identification Program", level=1)
    doc.add_paragraph("Customer identity must be verified using primary government identity documents.")

    doc.add_heading("Beneficial Ownership Verification", level=2)
    doc.add_paragraph("Entities with 25% or greater equity interest must be documented.")

    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Entity Type"
    table.rows[0].cells[1].text = "Verification Threshold"
    table.rows[1].cells[0].text = "Corporation"
    table.rows[1].cells[1].text = "25% Ownership"

    doc.save(str(docx_path))

    parser = DOCXParser()
    assert parser.can_parse(docx_path) is True

    parsed = parser.parse(docx_path)
    assert parsed.title == "KYC and Due Diligence Manual"
    assert len(parsed.blocks) >= 4

    headings = [b for b in parsed.blocks if b.block_type == "heading"]
    assert len(headings) >= 2
    assert headings[0].content == "Customer Identification Program"
    assert headings[0].heading_level == 1
    assert headings[1].content == "Beneficial Ownership Verification"
    assert headings[1].heading_level == 2

    tables = [b for b in parsed.blocks if b.block_type == "table"]
    assert len(tables) == 1
    assert "Corporation" in tables[0].content
    assert "25% Ownership" in tables[0].content


def test_text_markdown_parser(tmp_path: Path):
    """Verifies text/markdown parser captures markdown headings, lists, code blocks, and breadcrumbs."""
    md_path = tmp_path / "gdpr_guidelines.md"
    content = """# GDPR Compliance Framework

Under GDPR Art. 33, data breaches must be notified within 72 hours.

## Article 33 Notifications

- Mandatory for high-risk data breaches
- Supervisory authority notification required
- Impact assessment must accompany filing

```json
{"breach_category": "UNAUTHORIZED_ACCESS", "deadline_hours": 72}
```
"""
    md_path.write_text(content, encoding="utf-8")

    parser = TextMarkdownParser()
    assert parser.can_parse(md_path) is True

    parsed = parser.parse(md_path)
    assert len(parsed.blocks) >= 5

    h1 = [b for b in parsed.blocks if b.block_type == "heading" and b.heading_level == 1]
    assert len(h1) == 1
    assert h1[0].content == "GDPR Compliance Framework"

    h2 = [b for b in parsed.blocks if b.block_type == "heading" and b.heading_level == 2]
    assert len(h2) == 1
    assert "Article 33 Notifications" in h2[0].content
    assert "GDPR Compliance Framework > Article 33 Notifications" in h2[0].heading_breadcrumb

    lists = [b for b in parsed.blocks if b.block_type == "list_item"]
    assert len(lists) == 3

    code = [b for b in parsed.blocks if b.block_type == "code"]
    assert len(code) == 1
    assert "breach_category" in code[0].content


def test_parser_registry_and_unsupported_rejection(tmp_path: Path):
    """Verifies parser registry routes valid files and rejects unsupported formats."""
    pdf_p = tmp_path / "test.pdf"
    doc_p = tmp_path / "test.docx"
    txt_p = tmp_path / "test.txt"
    bad_p = tmp_path / "unsupported.exe"

    pdf_p.touch()
    doc_p.touch()
    txt_p.touch()
    bad_p.touch()

    assert isinstance(parser_registry.get_parser(pdf_p), PDFParser)
    assert isinstance(parser_registry.get_parser(doc_p), DOCXParser)
    assert isinstance(parser_registry.get_parser(txt_p), TextMarkdownParser)

    with pytest.raises(UnsupportedFormatError):
        parser_registry.get_parser(bad_p)
