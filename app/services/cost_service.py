"""
FinTrust RAG - Enterprise LLM Cost Telemetry & Calculation Service
Accurately calculates input, cached, output, and total monetary costs
using configurable, versioned pricing tables with high-precision Decimal arithmetic.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Standard 6-decimal precision for micro-cent accounting
PRECISION = Decimal("0.000001")
ONE_MILLION = Decimal("1000000")


@dataclass
class LLMCostBreakdown:
    provider: str
    model: str
    pricing_version: str
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int
    input_cost: Decimal
    output_cost: Decimal
    total_cost: Decimal
    is_known_model: bool


class CostService:
    """Provider-aware, versioned LLM cost calculation and aggregation engine."""

    def __init__(self, pricing_config_path: Optional[str] = None):
        self.pricing_config_path = pricing_config_path or "config/llm_pricing.json"
        self._load_pricing()

    def _load_pricing(self):
        """Loads versioned pricing configuration from JSON file or provides resilient defaults."""
        path = Path(self.pricing_config_path)
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                    self.version = self.config.get("version", "2026-03-enterprise")
                    self.rates = self.config.get("rates_per_million_tokens", {})
                    self.fallback = self.config.get("fallback_rates", {
                        "input_per_million": "0.000000",
                        "cached_input_per_million": "0.000000",
                        "output_per_million": "0.000000"
                    })
                    return
            except Exception as e:
                logger.warning(f"Failed to load pricing config from {path}: {e}. Falling back to default rates.")

        # Built-in fallback pricing
        self.version = "2026-03-builtin"
        self.rates = {
            "openai": {
                "gpt-4o-mini": {
                    "input_per_million": "0.150000",
                    "cached_input_per_million": "0.075000",
                    "output_per_million": "0.600000"
                },
                "gpt-4o": {
                    "input_per_million": "2.500000",
                    "cached_input_per_million": "1.250000",
                    "output_per_million": "10.000000"
                }
            },
            "anthropic": {
                "claude-3-5-sonnet-20241022": {
                    "input_per_million": "3.000000",
                    "cached_input_per_million": "0.300000",
                    "output_per_million": "15.000000"
                },
                "claude-3-5-haiku-20241022": {
                    "input_per_million": "0.800000",
                    "cached_input_per_million": "0.080000",
                    "output_per_million": "4.000000"
                }
            },
            "mock": {
                "mock-model": {
                    "input_per_million": "0.000000",
                    "cached_input_per_million": "0.000000",
                    "output_per_million": "0.000000"
                }
            }
        }
        self.fallback = {
            "input_per_million": "0.000000",
            "cached_input_per_million": "0.000000",
            "output_per_million": "0.000000"
        }

    def calculate_cost(
        self,
        provider: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int = 0
    ) -> LLMCostBreakdown:
        """Calculates precise monetary cost for an LLM execution step using Decimal arithmetic."""
        prov_key = (provider or "unknown").lower().strip()
        model_key = (model or "unknown").lower().strip()

        # Handle mock provider explicitly
        if prov_key == "mock" or "mock" in model_key:
            return LLMCostBreakdown(
                provider="mock",
                model=model,
                pricing_version=self.version,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                cached_prompt_tokens=cached_prompt_tokens,
                input_cost=Decimal("0.000000"),
                output_cost=Decimal("0.000000"),
                total_cost=Decimal("0.000000"),
                is_known_model=True
            )

        # Lookup rates for provider and model
        provider_rates = self.rates.get(prov_key, {})
        model_rate = None

        # Exact match
        if model_key in provider_rates:
            model_rate = provider_rates[model_key]
        else:
            # Prefix / family match (e.g. gpt-4o-mini-2024-07-18 -> gpt-4o-mini)
            for m_name, m_rates in provider_rates.items():
                if model_key.startswith(m_name) or m_name in model_key:
                    model_rate = m_rates
                    break

        is_known = model_rate is not None
        if not is_known:
            model_rate = self.fallback

        # Extract rates as Decimal
        input_rate = Decimal(str(model_rate.get("input_per_million", "0.000000")))
        cached_rate = Decimal(str(model_rate.get("cached_input_per_million", input_rate)))
        output_rate = Decimal(str(model_rate.get("output_per_million", "0.000000")))

        # Calculate tokens
        prompt_dec = Decimal(str(max(0, prompt_tokens)))
        cached_dec = Decimal(str(max(0, min(cached_prompt_tokens, prompt_tokens))))
        uncached_prompt_dec = prompt_dec - cached_dec
        completion_dec = Decimal(str(max(0, completion_tokens)))

        # Precise calculations
        input_cost = (
            (uncached_prompt_dec * input_rate / ONE_MILLION) +
            (cached_dec * cached_rate / ONE_MILLION)
        ).quantize(PRECISION, rounding=ROUND_HALF_UP)

        output_cost = (
            completion_dec * output_rate / ONE_MILLION
        ).quantize(PRECISION, rounding=ROUND_HALF_UP)

        total_cost = (input_cost + output_cost).quantize(PRECISION, rounding=ROUND_HALF_UP)

        return LLMCostBreakdown(
            provider=prov_key,
            model=model,
            pricing_version=self.version if is_known else f"{self.version}-fallback",
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            is_known_model=is_known
        )


cost_service = CostService()
