# FINTRUST RAG — LLM COST & TOKEN TELEMETRY REPORT

**Author**: Principal AI Infrastructure Engineer & Backend Architect  
**Date**: November 15, 2026  
**System**: FinTrust RAG — Telemetry & Observability Subsystem  
**Milestone**: Phase 7.6 Cost Telemetry Verification  

---

## 1. ARCHITECTURAL OVERVIEW

In Phase 7.5, audit findings revealed that FinTrust RAG lacked monetary cost accounting and prompt caching telemetry. In enterprise compliance and financial intelligence platforms, financial audibility, per-tenant margin calculation, and LLM budget enforcement are mission-critical.

In Phase 7.6, a complete, versioned micro-cent LLM cost accounting subsystem was implemented:
- **Exact Decimal Arithmetic**: Floating-point rounding errors are prohibited. All calculations use Python `Decimal` quantized to 6 decimal places (`0.000001` precision).
- **Prompt Caching Support**: Differentiates between raw prompt tokens and cached prompt tokens (which receive provider discounts up to 50–90%).
- **Model Fallback Logic**: Unknown or newly released models fall back to conservative tier-based rates with logged telemetry warnings.
- **Hierarchical Persistence**: Cost and token metrics are persisted both per-execution-trace (sub-agent tool invocations, synthesis steps) and aggregated at the root workflow level.

---

## 2. PRICING CATALOG SPECIFICATION (`config/llm_pricing.json`)

The catalog defines per-million-token costs in USD:

```json
{
  "version": "2026-11-v1",
  "effective_date": "2026-11-15",
  "rates": {
    "openai": {
      "gpt-4o": { "input": 2.50, "output": 10.00, "cached_input": 1.25 },
      "gpt-4o-mini": { "input": 0.15, "output": 0.60, "cached_input": 0.075 },
      "o1": { "input": 15.00, "output": 60.00, "cached_input": 7.50 },
      "o3-mini": { "input": 1.10, "output": 4.40, "cached_input": 0.55 }
    },
    "anthropic": {
      "claude-3-5-sonnet-20241022": { "input": 3.00, "output": 15.00, "cached_input": 0.30 },
      "claude-3-5-haiku-20241022": { "input": 1.00, "output": 5.00, "cached_input": 0.10 },
      "claude-3-opus-20240229": { "input": 15.00, "output": 75.00, "cached_input": 1.50 }
    },
    "mock": {
      "mock-llm": { "input": 0.0, "output": 0.0, "cached_input": 0.0 }
    },
    "_fallback": {
      "default": { "input": 2.50, "output": 10.00, "cached_input": 1.25 }
    }
  }
}
```

---

## 3. DATABASE SCHEMA & ALEMBIC MIGRATION

Alembic migration `migrations/versions/004_llm_cost_telemetry.py` added the following columns:

### 3.1 `AgenticWorkflow` Table
- `total_estimated_cost`: `NUMERIC(12, 6)` — Aggregated dollar cost of all sub-agent steps in the workflow.
- `llm_provider`: `VARCHAR(50)` — Primary LLM provider utilized (e.g., `openai`, `anthropic`, `mock`).
- `llm_model`: `VARCHAR(100)` — Primary model identifier.

### 3.2 `AgenticExecutionTrace` Table
- `prompt_tokens`: `INTEGER` — Number of non-cached prompt tokens.
- `completion_tokens`: `INTEGER` — Number of generated completion tokens.
- `total_tokens`: `INTEGER` — Sum of prompt + completion tokens.
- `cached_prompt_tokens`: `INTEGER` — Prompt tokens served from provider cache.
- `input_cost`: `NUMERIC(12, 6)` — Dollar cost of input tokens.
- `output_cost`: `NUMERIC(12, 6)` — Dollar cost of output tokens.
- `total_cost`: `NUMERIC(12, 6)` — Total cost (`input_cost + output_cost`).
- `pricing_version`: `VARCHAR(50)` — Version of pricing catalog applied (e.g., `2026-11-v1`).

---

## 4. SAMPLE CALCULATIONS & TEST SUITE VERIFICATION

All 8 tests in `app/tests/test_llm_cost_telemetry.py` passed with 100% accuracy:

### 4.1 Sample Calculation 1: OpenAI `gpt-4o`
- **Tokens**: 1,000 prompt tokens, 500 completion tokens, 0 cached tokens.
- **Input Cost**: `(1000 / 1,000,000) * $2.50 = $0.002500`
- **Output Cost**: `(500 / 1,000,000) * $10.00 = $0.005000`
- **Total Cost**: `$0.007500` (Exact `Decimal`)

### 4.2 Sample Calculation 2: Anthropic `claude-3-5-sonnet` with Cached Tokens
- **Tokens**: 2,000 prompt tokens, 1,000 completion tokens, 1,000 cached prompt tokens.
- **Input Cost**: `(1000 / 1,000,000) * $3.00 + (1000 / 1,000,000) * $0.30 = $0.003300`
- **Output Cost**: `(1000 / 1,000,000) * $15.00 = $0.015000`
- **Total Cost**: `$0.018300`

### 4.3 Sample Calculation 3: Mock Provider
- **Tokens**: 5,000 prompt tokens, 2,500 completion tokens.
- **Total Cost**: `$0.000000`

---

## 5. VERIFICATION VERDICT

**VERDICT: VERIFIED**

The LLM cost telemetry subsystem is fully operational, mathematically verified against floating-point inaccuracies, integrated into the database schema via migration `004`, and validated across all workflow and trace layers.
