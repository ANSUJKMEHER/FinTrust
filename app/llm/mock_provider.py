import re
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.llm.base import BaseLLMProvider, LLMMessage, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Deterministic, isolated mock provider for testing, CI, and evaluation benchmark runs."""

    def __init__(
        self,
        canned_response: Optional[str] = None,
        latency_simulation_ms: float = 2.0
    ):
        self.canned_response = canned_response
        self.latency_simulation_ms = latency_simulation_ms

    def generate(
        self,
        messages: List[LLMMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        start_time = time.perf_counter()

        # Custom canned response takes precedence
        if self.canned_response:
            content = self.canned_response
        else:
            # Combine all message text to extract evidence context and query
            full_text = " ".join(m.content for m in messages)
            user_msg = next((m.content for m in reversed(messages) if m.role.value == "user"), "")
            content = self._synthesize_grounded_mock_response(user_msg, full_text)

        # Small simulated latency
        if self.latency_simulation_ms > 0:
            time.sleep(self.latency_simulation_ms / 1000.0)

        latency_ms = (time.perf_counter() - start_time) * 1000.0
        prompt_tokens = sum(len(m.content.split()) for m in messages) * 2
        completion_tokens = len(content.split()) * 2

        return LLMResponse(
            content=content,
            model="fintrust-mock-v1",
            provider="mock",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            finish_reason="stop",
            raw_metadata={"mock": True}
        )

    def _synthesize_grounded_mock_response(self, query: str, context: str) -> str:
        """Synthesizes a realistic, grounded answer using the exact evidence in context."""
        # Extract pure user query without prompt wrapping
        if "User Question:" in query:
            clean_query = query.split("User Question:")[1].split("Provide a grounded")[0].strip()
        else:
            clean_query = query.strip()

        query_lower = clean_query.lower()

        # Check for empty evidence or completely unsupported query topics
        has_evidence = "evidence_id:" in context.lower() or "<evidence" in context.lower()
        if not has_evidence:
            return settings.RAG_REFUSAL_MESSAGE

        # Extract evidence blocks from prompt: [EVIDENCE_XXX] Title: ... Page: ... Section: ...
        evidence_blocks = re.findall(
            r'\[(EVIDENCE_\d+)\].*?Title:\s*([^\n]+).*?Page:\s*([^\n]+).*?Section:\s*([^\n]+).*?Content:\s*([^\n]+(?:\n(?:(?!\[EVIDENCE_|\n\n)[^\n]+))*)',
            context,
            re.DOTALL
        )

        if not evidence_blocks:
            # Try alternate XML format: <evidence id="EVIDENCE_XXX" ...>
            xml_blocks = re.findall(
                r'<evidence id="([^"]+)" document="([^"]+)" page="([^"]*)" section="([^"]*)">\s*(.*?)\s*</evidence>',
                context,
                re.DOTALL
            )
            evidence_blocks = [
                (b[0], b[1], b[2] if b[2] else "N/A", b[3] if b[3] else "General", b[4])
                for b in xml_blocks
            ]

        # 1. SAR / Suspicious Activity & BSA Section 5318(g)
        if any(k in query_lower for k in ["sar", "suspicious", "5318", "threshold", "filing window"]):
            target = next((b for b in evidence_blocks if "5318" in b[4] or "sar" in b[4].lower() or "suspicious" in b[4].lower()), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                sentences = []
                form_part = " using FinCEN Form 111" if "111" in text else ""
                sentences.append(f"Under BSA Section 5318(g) and 31 CFR 1020.320, covered financial institutions must file a Suspicious Activity Report (SAR){form_part} within 30 calendar days {cit}.")
                if "$5,000" in text:
                    sentences.append(f"For transactions aggregating $5,000 or greater, the mandatory filing window is 30 calendar days {cit}.")
                if "$25,000" in text:
                    sentences.append(f"In cases involving an unknown suspect aggregating $25,000 or more, institutions have 60 calendar days to complete filing {cit}.")
                return " ".join(sentences)

        # 2. GDPR Article 33 Breach Notification
        if any(k in query_lower for k in ["gdpr", "article 33", "breach", "72 hours"]):
            target = next((b for b in evidence_blocks if "33" in b[4] or "72 hours" in b[4] or "breach" in b[4].lower()), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                return (
                    f"Pursuant to GDPR Article 33, financial institutions must notify the competent supervisory authority "
                    f"of a personal data security breach within 72 hours of becoming aware of the incident {cit}. "
                    f"Any notification submitted after 72 hours must be accompanied by explicit reasons for the delay {cit}."
                )

        # 3. Basel III Liquidity Coverage Ratio (LCR)
        if any(k in query_lower for k in ["basel", "liquidity coverage ratio", "lcr", "stress period", "minimum floor"]):
            target = next((b for b in evidence_blocks if "lcr" in b[4].lower() or "liquidity" in b[4].lower()), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                return (
                    f"Under the Basel III liquidity framework, the Liquidity Coverage Ratio (LCR) mandates that institutions "
                    f"maintain unencumbered High-Quality Liquid Assets (HQLA) equal to or exceeding total net cash outflows "
                    f"over a 30-day stress period {cit}. "
                    f"The required regulatory minimum floor for the LCR is strictly 100 percent {cit}."
                )

        # 4. Trade-Based Money Laundering (TBML)
        if any(k in query_lower for k in ["trade-based", "tbml", "red flag", "invoiced value", "shell company"]):
            target = next((b for b in evidence_blocks if "trade" in b[4].lower() or "shell" in b[4].lower()), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                return (
                    f"According to FinCEN Advisory FIN-2023-A001, primary red flags for trade-based money laundering (TBML) "
                    f"include significant discrepancies between invoiced value and fair market value {cit}. "
                    f"Institutions must also monitor high-velocity wire transfers routed through shell companies in high-risk jurisdictions {cit}."
                )

        # 5. Customer Due Diligence (CDD) & Beneficial Ownership
        if any(k in query_lower for k in ["cdd", "beneficial owner", "25 percent", "1010.230"]):
            target = next((b for b in evidence_blocks if "25 percent" in b[4] or "beneficial" in b[4].lower()), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                return (
                    f"Under the FinCEN CDD Rule (31 CFR 1010.230), financial institutions must identify and verify "
                    f"the identity of each beneficial owner who owns directly or indirectly 25 percent or more of equity interests {cit}."
                )

        # 6. Currency Transaction Report (CTR) & Structuring
        if any(k in query_lower for k in ["ctr", "currency transaction", "$10,000", "structuring"]):
            target = next((b for b in evidence_blocks if "10,000" in b[4] or "structuring" in b[4].lower()), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                return (
                    f"Financial institutions must submit a Currency Transaction Report (CTR) for currency transactions exceeding "
                    f"$10,000 conducted in a single business day {cit}. "
                    f"Structuring transactions to evade this $10,000 threshold constitutes a statutory violation requiring SAR filing {cit}."
                )

        # 7. Dodd-Frank Title VII Derivatives
        if any(k in query_lower for k in ["dodd-frank", "title vii", "swap", "sdr", "mandatory clearing"]):
            target = next((b for b in evidence_blocks if "title vii" in b[4].lower() or "swap" in b[4].lower()), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                return (
                    f"Dodd-Frank Title VII mandates real-time public reporting of swap transactions to registered Swap Data "
                    f"Repositories (SDR) and establishes mandatory clearing for standardized derivatives {cit}."
                )

        # 8. Sarbanes-Oxley (SOX) Section 404 & 302
        if any(k in query_lower for k in ["sox", "404", "302", "internal control", "icfr", "certification"]):
            target = next((b for b in evidence_blocks if "404" in b[4] or "302" in b[4]), None)
            if target:
                eid, title, page, section, text = target
                cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                return (
                    f"Section 404 of the Sarbanes-Oxley Act requires annual management reports on Internal Control over Financial "
                    f"Reporting (ICFR), while Section 302 mandates quarterly CEO and CFO certification of disclosure controls {cit}."
                )

        # If evidence blocks exist but do not match the query topic -> principled refusal
        if evidence_blocks:
            # Check if any evidence block has substantive keyword overlap (at least 50% of query keywords)
            q_words = set(re.findall(r'\b\w{4,}\b', query_lower))
            matched_any = False
            for b in evidence_blocks:
                b_words = set(re.findall(r'\b\w{4,}\b', b[4].lower()))
                common = q_words.intersection(b_words)
                overlap_ratio = len(common) / max(1, len(q_words))
                if overlap_ratio >= 0.50 and len(common) >= 3:
                    matched_any = True
                    eid, title, page, section, text = b
                    cit = f"[{title.strip()}, {section.strip()}, Page {page.strip()}]"
                    return f"Based on the provided documents: {text.strip()[:200]}... {cit}"

            if not matched_any:
                return settings.RAG_REFUSAL_MESSAGE

        return settings.RAG_REFUSAL_MESSAGE

    def health_check(self) -> Dict[str, Any]:
        return {
            "provider": "mock",
            "model": "fintrust-mock-v1",
            "status": "healthy",
            "latency_ms": self.latency_simulation_ms
        }
