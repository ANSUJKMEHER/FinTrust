import pytest
from app.parsers.base import ParsedBlock, ParsedDocument
from app.services.chunking_service import ChunkingService


def test_chunking_heading_preservation_and_breadcrumbs():
    """Verifies headings flush previous chunks and attach breadcrumbs to subsequent chunks."""
    doc = ParsedDocument(
        title="AML Manual",
        blocks=[
            ParsedBlock(
                block_type="heading",
                content="Section 1: Suspicious Transactions",
                heading_level=1,
                section_heading="Section 1: Suspicious Transactions",
                heading_breadcrumb="Section 1: Suspicious Transactions"
            ),
            ParsedBlock(
                block_type="paragraph",
                content="Financial institutions must monitor all account transactions exceeding $10,000.",
                section_heading="Section 1: Suspicious Transactions",
                heading_breadcrumb="Section 1: Suspicious Transactions",
                page_number=1
            ),
            ParsedBlock(
                block_type="heading",
                content="Section 2: SAR Filing Deadlines",
                heading_level=1,
                section_heading="Section 2: SAR Filing Deadlines",
                heading_breadcrumb="Section 2: SAR Filing Deadlines"
            ),
            ParsedBlock(
                block_type="paragraph",
                content="SAR filings under FinCEN Form 111 must be submitted within 30 days of initial detection.",
                section_heading="Section 2: SAR Filing Deadlines",
                heading_breadcrumb="Section 2: SAR Filing Deadlines",
                page_number=2
            )
        ]
    )

    chunker = ChunkingService(target_chunk_tokens=50, overlap_tokens=10)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert "Section 1" in chunks[0].content
    assert chunks[0].section_heading == "Section 1: Suspicious Transactions"
    assert chunks[0].page_number == 1

    assert chunks[1].chunk_index == 1
    assert "Section 2" in chunks[1].content
    assert chunks[1].section_heading == "Section 2: SAR Filing Deadlines"
    assert chunks[1].page_number == 2


def test_chunking_table_preservation():
    """Verifies tables are kept whole as discrete coherent units."""
    table_content = (
        "| Regulation | Identifier | Timetable |\n"
        "| --- | --- | --- |\n"
        "| BSA | Section 5318(g) | 30 days |\n"
        "| GDPR | Article 33 | 72 hours |"
    )
    doc = ParsedDocument(
        blocks=[
            ParsedBlock(
                block_type="table",
                content=table_content,
                page_number=3,
                section_heading="Regulatory Table",
                heading_breadcrumb="Compliance > Regulatory Table"
            )
        ]
    )

    chunker = ChunkingService(target_chunk_tokens=200, overlap_tokens=20)
    chunks = chunker.chunk_document(doc)

    assert len(chunks) == 1
    assert chunks[0].content == table_content
    assert chunks[0].page_number == 3
    assert chunks[0].section_heading == "Regulatory Table"


def test_chunking_sentence_splitting_with_regulatory_abbreviations():
    """Verifies legal and regulatory abbreviations like 'Art.', 'Sec.', 'No.' do not cause split sentence errors."""
    chunker = ChunkingService(target_chunk_tokens=100, overlap_tokens=20)
    text = (
        "Compliance officers must review Art. 33 of GDPR immediately. "
        "Furthermore, Sec. 5318(g) of the BSA mandates reporting under Form No. 111. "
        "Any delay will result in severe regulatory fines."
    )
    sentences = chunker.split_into_sentences(text)
    assert len(sentences) == 3
    assert sentences[0].startswith("Compliance officers must review Art. 33")
    assert sentences[1].startswith("Furthermore, Sec. 5318(g) of the BSA mandates reporting under Form No. 111.")
    assert sentences[2].startswith("Any delay will result")


def test_chunking_determinism():
    """Verifies chunking is 100% deterministic: identical document produces identical chunks and hashes."""
    doc = ParsedDocument(
        blocks=[
            ParsedBlock(block_type="paragraph", content="First sentence of regulatory text."),
            ParsedBlock(block_type="paragraph", content="Second sentence with numeric threshold $50,000.")
        ]
    )

    chunker = ChunkingService(target_chunk_tokens=20, overlap_tokens=5)
    run1 = chunker.chunk_document(doc)
    run2 = chunker.chunk_document(doc)

    assert len(run1) == len(run2)
    for c1, c2 in zip(run1, run2):
        assert c1.chunk_index == c2.chunk_index
        assert c1.content == c2.content
        assert c1.content_hash == c2.content_hash
        assert c1.token_count == c2.token_count
