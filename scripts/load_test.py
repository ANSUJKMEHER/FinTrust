import argparse
import asyncio
from datetime import datetime, timezone
import json
import statistics
import time
from typing import Any, Dict, List
import logging
import httpx
from sqlalchemy.orm import Session

# Suppress verbose SQL query logging during benchmark runs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("fintrust").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import SessionLocal
from app.main import app
from app.services.embedding_service import EmbeddingService
from app.services.reranking_service import RerankingService


class FinTrustLoadTester:
    """Benchmark and load testing suite for FinTrust RAG."""

    def __init__(self, concurrency: int = 5, total_requests: int = 50):
        self.concurrency = concurrency
        self.total_requests = total_requests
        self.results: Dict[str, List[float]] = {}
        self.errors: Dict[str, int] = {}
        self.auth_token = self._generate_bench_token()

    def warmup(self):
        """Pre-warms ML models to isolate runtime inference from cold-start weight downloads."""
        print("[*] Pre-warming neural embedding and reranking models...")
        try:
            EmbeddingService.get_model(settings.EMBEDDING_MODEL_NAME)
            RerankingService.get_model(settings.RERANKING_MODEL_NAME)
            print("[+] Models initialized and ready for benchmark.")
        except Exception as e:
            print(f"[!] Warmup warning: {e}")

    def _generate_bench_token(self) -> str:
        """Retrieves or creates a benchmark user token from PostgreSQL."""
        with SessionLocal() as db:
            user = db.query(User).first()
            if not user:
                # Seed temporary tenant and user
                tenant = Tenant(name="Benchmark Tenant", slug="bench-tenant")
                db.add(tenant)
                db.flush()
                user = User(
                    tenant_id=tenant.id,
                    email="benchmark@fintrust.ai",
                    hashed_password="hashed_placeholder_for_benchmarking",
                    full_name="Benchmark Worker",
                    is_active=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)

            token = create_access_token(
                subject=str(user.id),
                tenant_id=str(user.tenant_id),
                roles=["ADMIN"]
            )
            return token

    async def run_scenario(
        self,
        name: str,
        method: str,
        url: str,
        json_body: Dict[str, Any] = None,
        headers: Dict[str, str] = None,
        count: int = 50
    ) -> Dict[str, Any]:
        print(f"\n[*] Running Benchmark: {name} ({count} requests, concurrency={self.concurrency})...")
        latencies: List[float] = []
        error_count = 0
        semaphore = asyncio.Semaphore(self.concurrency)

        client_headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
            **(headers or {})
        }

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=True) as client:
            async def worker():
                nonlocal error_count
                async with semaphore:
                    t0 = time.perf_counter()
                    try:
                        if method.upper() == "GET":
                            resp = await client.get(url, headers=client_headers, timeout=30.0)
                        elif method.upper() == "POST":
                            resp = await client.post(url, json=json_body, headers=client_headers, timeout=30.0)
                        else:
                            raise ValueError(f"Unsupported method: {method}")

                        duration = (time.perf_counter() - t0) * 1000.0  # ms
                        if resp.status_code in (200, 201):
                            latencies.append(duration)
                        else:
                            error_count += 1
                    except Exception as ex:
                        error_count += 1

            t_start = time.perf_counter()
            tasks = [worker() for _ in range(count)]
            await asyncio.gather(*tasks)
            total_duration = time.perf_counter() - t_start

        if not latencies:
            print(f"[!] Scenario {name} failed: 0 successful requests (Errors: {error_count})")
            return {"name": name, "success_count": 0, "error_count": error_count, "rps": 0.0}

        sorted_lat = sorted(latencies)
        p50 = statistics.median(sorted_lat)
        p90 = sorted_lat[int(len(sorted_lat) * 0.90)]
        p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
        p99 = sorted_lat[min(int(len(sorted_lat) * 0.99), len(sorted_lat) - 1)]
        mean = statistics.mean(sorted_lat)
        rps = len(latencies) / total_duration if total_duration > 0 else 0.0

        summary = {
            "name": name,
            "requests": count,
            "successful": len(latencies),
            "errors": error_count,
            "error_rate_pct": (error_count / count) * 100.0,
            "total_duration_sec": round(total_duration, 3),
            "throughput_rps": round(rps, 2),
            "latency_p50_ms": round(p50, 2),
            "latency_p90_ms": round(p90, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "latency_mean_ms": round(mean, 2),
        }

        print(f"    [+] Completed in {summary['total_duration_sec']}s | Throughput: {summary['throughput_rps']} req/s")
        print(f"    [+] P50: {summary['latency_p50_ms']}ms | P95: {summary['latency_p95_ms']}ms | P99: {summary['latency_p99_ms']}ms")
        print(f"    [+] Errors: {summary['errors']} ({summary['error_rate_pct']}%)")
        return summary


async def run_full_benchmark() -> List[Dict[str, Any]]:
    tester = FinTrustLoadTester(concurrency=5, total_requests=50)
    tester.warmup()

    summaries = []

    # 1. Health Probe Benchmark
    summaries.append(await tester.run_scenario(
        name="Liveness Probe (/health/live)",
        method="GET",
        url="/health/live",
        count=100
    ))

    # 2. Authenticated Profile Fetch
    summaries.append(await tester.run_scenario(
        name="User Profile Fetch (/api/v1/auth/me)",
        method="GET",
        url="/api/v1/auth/me",
        count=50
    ))

    # 3. Document Listing & Tenant Scoping
    summaries.append(await tester.run_scenario(
        name="Document Listing (/api/v1/documents/)",
        method="GET",
        url="/api/v1/documents/",
        count=50
    ))

    # 4. Hybrid Retrieval (Vector + Full-Text + RRF)
    summaries.append(await tester.run_scenario(
        name="Hybrid Search Retrieval (/api/v1/search/hybrid)",
        method="POST",
        url="/api/v1/search/hybrid",
        json_body={"query": "BSA SAR reporting requirements compliance", "limit": 5},
        count=30
    ))

    # 5. Full Grounded RAG Query Pipeline
    summaries.append(await tester.run_scenario(
        name="Grounded RAG Pipeline (/api/v1/rag/query)",
        method="POST",
        url="/api/v1/rag/query",
        json_body={
            "query": "What are the regulatory filing deadlines for suspicious activity?",
            "max_chunks": 5
        },
        count=20
    ))

    # 6. Multi-Agent Workflow Execution
    summaries.append(await tester.run_scenario(
        name="Multi-Agent Compliance Workflow (/api/v1/agentic/compliance-audit)",
        method="POST",
        url="/api/v1/agentic/compliance-audit",
        json_body={
            "query": "Verify FinCEN SAR filing compliance deadlines and threshold policy",
            "statute_reference": "BSA Section 5318(g)",
            "require_human_approval": False
        },
        count=15
    ))

    # Save benchmark report to JSON
    report_file = "PERFORMANCE_BENCHMARK_RESULTS.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "concurrency": 10,
            "database": settings.POSTGRES_DB,
            "scenarios": summaries
        }, f, indent=2)

    print(f"\n[+] Full benchmark results saved to {report_file}")
    return summaries


if __name__ == "__main__":
    asyncio.run(run_full_benchmark())
