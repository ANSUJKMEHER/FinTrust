"""
Conflict Resolution Engine: Detects and documents contradictions between policy versions,
statutory standards, and financial thresholds across multi-document evidence.
"""
import re
import time
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.agentic.state import (
    AgenticWorkflowState,
    ComplianceFinding,
    DocumentComparisonFinding,
    EvidenceRegistryItem,
    IdentifiedConflict,
)


class ConflictResolutionEngine:
    """Detects and reconciles contradictory evidence across documents without discarding conflicts."""

    CURRENCY_REGEX = re.compile(r'\$[0-9,]+', re.IGNORECASE)
    DEADLINE_REGEX = re.compile(r'\b[0-9]+\s+(?:calendar\s+|business\s+)?(?:days|hours|months)\b', re.IGNORECASE)

    def detect_and_resolve_conflicts(
        self,
        state: AgenticWorkflowState,
        db: Optional[Session] = None
    ) -> List[IdentifiedConflict]:
        """Scans compliance findings, comparisons, and evidence items for substantive contradictions."""
        conflicts: List[IdentifiedConflict] = []
        conflict_idx = 1

        evidence_registry = state.get("evidence_registry", {})
        compliance_findings = state.get("compliance_findings", [])
        document_comparisons = state.get("document_comparisons", []) or state.get("comparison_findings", [])

        # 1. Inspect DocumentComparison findings for detected differences
        for comp in document_comparisons:
            ftype = comp.get("finding_type", "")
            if ftype in ("THRESHOLD_MODIFIED", "DEADLINE_MODIFIED", "OBLIGATION_REMOVED"):
                conf: IdentifiedConflict = {
                    "conflict_id": f"CONF_{conflict_idx:03d}",
                    "conflict_type": (
                        "THRESHOLD_DISCREPANCY" if "THRESHOLD" in ftype
                        else "DEADLINE_DISCREPANCY" if "DEADLINE" in ftype
                        else "OBLIGATION_CONTRADICTION"
                    ),
                    "description": comp.get("description", "Cross-document policy modification detected."),
                    "item_a": {
                        "document_title": comp.get("doc1_title", "Baseline Document"),
                        "statement": comp.get("doc1_statement"),
                        "citation": comp.get("doc1_citation"),
                    },
                    "item_b": {
                        "document_title": comp.get("doc2_title", "Comparison Document"),
                        "statement": comp.get("doc2_statement"),
                        "citation": comp.get("doc2_citation"),
                    },
                    "severity": "HIGH" if "THRESHOLD" in ftype or "DEADLINE" in ftype else "MEDIUM",
                    "requires_human_review": True,
                    "resolution_status": "ESCALATED_TO_HUMAN",
                    "reconciliation_notes": (
                        f"Discrepancy identified between '{comp.get('doc1_title')}' and '{comp.get('doc2_title')}'. "
                        "Preserving both statements with explicit citations; requiring compliance officer verification."
                    )
                }
                conflicts.append(conf)
                conflict_idx += 1

        # 2. Inspect Compliance Findings for conflicting thresholds across different evidence chunks
        threshold_map: Dict[str, List[Dict[str, Any]]] = {}
        deadline_map: Dict[str, List[Dict[str, Any]]] = {}

        for f in compliance_findings:
            th = f.get("financial_threshold")
            dl = f.get("filing_deadline")
            eids = f.get("supporting_evidence_ids", [])
            cit = f.get("citations", ["N/A"])[0]

            if th and eids:
                doc_title = evidence_registry.get(eids[0], {}).get("document_title", "Unknown")
                threshold_map.setdefault(th, []).append({
                    "finding_id": f["finding_id"],
                    "text": f["requirement_text"],
                    "citation": cit,
                    "doc_title": doc_title,
                })

            if dl and eids:
                doc_title = evidence_registry.get(eids[0], {}).get("document_title", "Unknown")
                deadline_map.setdefault(dl, []).append({
                    "finding_id": f["finding_id"],
                    "text": f["requirement_text"],
                    "citation": cit,
                    "doc_title": doc_title,
                })

        # If distinct threshold values exist for overlapping topics in different documents
        if len(threshold_map) >= 2:
            th_keys = list(threshold_map.keys())
            doc_a = threshold_map[th_keys[0]][0]
            doc_b = threshold_map[th_keys[1]][0]

            if doc_a["doc_title"] != doc_b["doc_title"]:
                conf: IdentifiedConflict = {
                    "conflict_id": f"CONF_{conflict_idx:03d}",
                    "conflict_type": "THRESHOLD_DISCREPANCY",
                    "description": f"Multiple contradictory financial thresholds identified across documents: {th_keys[0]} vs {th_keys[1]}.",
                    "item_a": {
                        "document_title": doc_a["doc_title"],
                        "statement": doc_a["text"],
                        "citation": doc_a["citation"],
                    },
                    "item_b": {
                        "document_title": doc_b["doc_title"],
                        "statement": doc_b["text"],
                        "citation": doc_b["citation"],
                    },
                    "severity": "HIGH",
                    "requires_human_review": True,
                    "resolution_status": "ESCALATED_TO_HUMAN",
                    "reconciliation_notes": (
                        f"Document '{doc_a['doc_title']}' specifies {th_keys[0]} while document '{doc_b['doc_title']}' specifies {th_keys[1]}. "
                        "Both provisions preserved without silent suppression."
                    )
                }
                conflicts.append(conf)
                conflict_idx += 1

        # If distinct deadline values exist for overlapping topics in different documents
        if len(deadline_map) >= 2:
            dl_keys = list(deadline_map.keys())
            doc_a = deadline_map[dl_keys[0]][0]
            doc_b = deadline_map[dl_keys[1]][0]

            if doc_a["doc_title"] != doc_b["doc_title"]:
                conf: IdentifiedConflict = {
                    "conflict_id": f"CONF_{conflict_idx:03d}",
                    "conflict_type": "DEADLINE_DISCREPANCY",
                    "description": f"Multiple contradictory filing deadlines identified across documents: {dl_keys[0]} vs {dl_keys[1]}.",
                    "item_a": {
                        "document_title": doc_a["doc_title"],
                        "statement": doc_a["text"],
                        "citation": doc_a["citation"],
                    },
                    "item_b": {
                        "document_title": doc_b["doc_title"],
                        "statement": doc_b["text"],
                        "citation": doc_b["citation"],
                    },
                    "severity": "HIGH",
                    "requires_human_review": True,
                    "resolution_status": "ESCALATED_TO_HUMAN",
                    "reconciliation_notes": (
                        f"Document '{doc_a['doc_title']}' specifies {dl_keys[0]} while document '{doc_b['doc_title']}' specifies {dl_keys[1]}. "
                        "Both provisions preserved without silent suppression."
                    )
                }
                conflicts.append(conf)
                conflict_idx += 1

        return conflicts

    # Alias for graph workflow integration
    detect_conflicts = detect_and_resolve_conflicts
