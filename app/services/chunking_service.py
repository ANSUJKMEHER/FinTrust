from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import List, Optional
import uuid

from app.core.config import settings
from app.parsers.base import ParsedBlock, ParsedDocument

logger = logging.getLogger(__name__)


@dataclass
class ChunkOutput:
    """Standard chunk representation ready for embedding and database persistence."""
    chunk_index: int
    content: str
    token_count: int
    content_hash: str
    page_number: Optional[int] = None
    section_heading: Optional[str] = None
    heading_breadcrumb: Optional[str] = None
    metadata: dict = field(default_factory=dict)


class ChunkingService:
    """Structure-aware, heading-preserving, deterministic text chunker for financial & regulatory documents."""

    # Sentence boundary regex with common abbreviation protections
    SENTENCE_SPLIT_REGEX = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
    ABBREVIATIONS = {"art.", "sec.", "no.", "u.s.", "e.g.", "i.e.", "al.", "corp.", "inc.", "ltd."}

    def __init__(
        self,
        target_chunk_tokens: int = settings.CHUNK_TARGET_SIZE_TOKENS,
        overlap_tokens: int = settings.CHUNK_OVERLAP_TOKENS
    ):
        self.target_tokens = target_chunk_tokens
        self.overlap_tokens = overlap_tokens

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Estimates token count deterministically using whitespace and punctuation tokens."""
        if not text:
            return 0
        words = re.findall(r"\w+|[^\w\s]", text)
        return max(1, len(words))

    @staticmethod
    def compute_hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def split_into_sentences(self, text: str) -> List[str]:
        """Splits paragraph text into sentences without breaking common legal/regulatory abbreviations."""
        raw_splits = self.SENTENCE_SPLIT_REGEX.split(text)
        merged: List[str] = []
        for s in raw_splits:
            s_clean = s.strip()
            if not s_clean:
                continue
            if merged and any(merged[-1].lower().endswith(abbr) for abbr in self.ABBREVIATIONS):
                merged[-1] = f"{merged[-1]} {s_clean}"
            else:
                merged.append(s_clean)
        return merged

    def chunk_document(self, parsed_doc: ParsedDocument) -> List[ChunkOutput]:
        """Chunks a ParsedDocument into deterministic, structure-aware ChunkOutput objects."""
        chunks: List[ChunkOutput] = []
        chunk_idx = 0

        current_sentences: List[str] = []
        current_tokens = 0
        current_page: Optional[int] = None
        current_heading: Optional[str] = None
        current_breadcrumb: Optional[str] = None

        def flush_chunk():
            nonlocal current_sentences, current_tokens, chunk_idx, current_page, current_heading, current_breadcrumb
            if not current_sentences:
                return

            chunk_text = " ".join(current_sentences).strip()
            if chunk_text:
                c_hash = self.compute_hash(chunk_text)
                chunks.append(
                    ChunkOutput(
                        chunk_index=chunk_idx,
                        content=chunk_text,
                        token_count=self.estimate_tokens(chunk_text),
                        content_hash=c_hash,
                        page_number=current_page,
                        section_heading=current_heading,
                        heading_breadcrumb=current_breadcrumb
                    )
                )
                chunk_idx += 1

            # Prepare overlap for next chunk
            overlap_sentences: List[str] = []
            overlap_count = 0
            for s in reversed(current_sentences):
                s_tokens = self.estimate_tokens(s)
                if overlap_count + s_tokens <= self.overlap_tokens:
                    overlap_sentences.insert(0, s)
                    overlap_count += s_tokens
                else:
                    break

            current_sentences = overlap_sentences
            current_tokens = overlap_count

        for block in parsed_doc.blocks:
            # 1. Handle Major Headings: Flush existing chunk to avoid merging unrelated sections
            if block.block_type == "heading":
                flush_chunk()
                current_heading = block.section_heading
                current_breadcrumb = block.heading_breadcrumb
                current_page = block.page_number
                # Headings are seeded into the start of the next section chunk
                current_sentences.append(block.content)
                current_tokens += self.estimate_tokens(block.content)
                continue

            # 2. Handle Tables: Keep tables whole if within budget; split rows preserving header if huge
            if block.block_type == "table":
                flush_chunk()  # Tables start fresh
                table_tokens = self.estimate_tokens(block.content)
                if table_tokens <= self.target_tokens:
                    chunks.append(
                        ChunkOutput(
                            chunk_index=chunk_idx,
                            content=block.content,
                            token_count=table_tokens,
                            content_hash=self.compute_hash(block.content),
                            page_number=block.page_number,
                            section_heading=block.section_heading or current_heading,
                            heading_breadcrumb=block.heading_breadcrumb or current_breadcrumb,
                            metadata=dict(block.metadata)
                        )
                    )
                    chunk_idx += 1
                else:
                    # Huge table: split row by row, repeating header
                    lines = block.content.splitlines()
                    if len(lines) >= 2:
                        header_lines = lines[:2]
                        header_tokens = self.estimate_tokens("\n".join(header_lines))
                        sub_table_rows = []
                        sub_table_tokens = header_tokens

                        for row_line in lines[2:]:
                            row_tokens = self.estimate_tokens(row_line)
                            if sub_table_tokens + row_tokens > self.target_tokens and sub_table_rows:
                                full_sub = "\n".join(header_lines + sub_table_rows)
                                chunks.append(
                                    ChunkOutput(
                                        chunk_index=chunk_idx,
                                        content=full_sub,
                                        token_count=self.estimate_tokens(full_sub),
                                        content_hash=self.compute_hash(full_sub),
                                        page_number=block.page_number,
                                        section_heading=block.section_heading or current_heading,
                                        heading_breadcrumb=block.heading_breadcrumb or current_breadcrumb,
                                        metadata=dict(block.metadata)
                                    )
                                )
                                chunk_idx += 1
                                sub_table_rows = [row_line]
                                sub_table_tokens = header_tokens + row_tokens
                            else:
                                sub_table_rows.append(row_line)
                                sub_table_tokens += row_tokens

                        if sub_table_rows:
                            full_sub = "\n".join(header_lines + sub_table_rows)
                            chunks.append(
                                ChunkOutput(
                                    chunk_index=chunk_idx,
                                    content=full_sub,
                                    token_count=self.estimate_tokens(full_sub),
                                    content_hash=self.compute_hash(full_sub),
                                    page_number=block.page_number,
                                    section_heading=block.section_heading or current_heading,
                                    heading_breadcrumb=block.heading_breadcrumb or current_breadcrumb,
                                    metadata=dict(block.metadata)
                                )
                            )
                            chunk_idx += 1
                continue

            # 3. Handle Standard Paragraphs, Lists, and Code
            if block.page_number:
                current_page = block.page_number
            if block.section_heading:
                current_heading = block.section_heading
            if block.heading_breadcrumb:
                current_breadcrumb = block.heading_breadcrumb

            sentences = self.split_into_sentences(block.content)
            for sentence in sentences:
                s_tokens = self.estimate_tokens(sentence)

                # Sentence alone exceeds target (e.g., massive unbroken run-on sentence)
                if s_tokens > self.target_tokens:
                    flush_chunk()
                    # Hard split on word boundaries
                    words = sentence.split()
                    sub_words: List[str] = []
                    sub_tokens = 0
                    for w in words:
                        w_tokens = self.estimate_tokens(w)
                        if sub_tokens + w_tokens > self.target_tokens and sub_words:
                            part_text = " ".join(sub_words)
                            chunks.append(
                                ChunkOutput(
                                    chunk_index=chunk_idx,
                                    content=part_text,
                                    token_count=self.estimate_tokens(part_text),
                                    content_hash=self.compute_hash(part_text),
                                    page_number=current_page,
                                    section_heading=current_heading,
                                    heading_breadcrumb=current_breadcrumb
                                )
                            )
                            chunk_idx += 1
                            sub_words = [w]
                            sub_tokens = w_tokens
                        else:
                            sub_words.append(w)
                            sub_tokens += w_tokens

                    if sub_words:
                        current_sentences = [" ".join(sub_words)]
                        current_tokens = sub_tokens
                    continue

                if current_tokens + s_tokens > self.target_tokens:
                    flush_chunk()

                current_sentences.append(sentence)
                current_tokens += s_tokens

        flush_chunk()
        return chunks
