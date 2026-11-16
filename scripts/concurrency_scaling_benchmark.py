import asyncio
import json
import logging
import os
import statistics
import time
from typing import Any, Dict, List
import httpx
import psutil
from sqlalchemy.orm import Session

# Suppress debug logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.ERROR)
logging.getLogger("fintrust").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.role import Role
from app.db.models.tenant import Tenant
from app.db.models.user import User
from app.db.session import SessionLocal, engine
from app.main import app


def get_process_metrics():
    proc = psutil.Process()
    mem_info = proc.memory_info()
    return {
        "rss_mb": round(mem_info.rss / (1024 * 1024), 2),
        "cpu_percent": psutil.cpu_percent(interval=None)
    }


def seed_bench_user() -> str:
    with SessionLocal() as db:
        role = db.query(Role).filter(Role.id == "ADMIN").first()
        if not role:
            role = Role(id="ADMIN", description="Admin")
            db.add(role)
            db.commit()

        tenant = db.query(Tenant).first()
        if not tenant:
            tenant = Tenant(name="Scaling Tenant", slug="scale-tenant")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)

        user = db.query(User).filter(User.tenant_id == tenant.id).first()
        if not user:
            user = User(
                tenant_id=tenant.id,
                email="concurrency_bench@fintrust.ai",
                hashed_password="mock_hash_for_benchmarking",
                full_name="Concurrency Worker",
                is_active=True,
                roles=[role]
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


async def benchmark_concurrency_tier(
    endpoint_name: str,
    url: str,
    token: str,
    concurrency: int,
    total_requests: int
) -> Dict[str, Any]:
    print(f"\n[*] Testing {endpoint_name} | Concurrency: {concurrency} | Total Requests: {total_requests}...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    latencies: List[float] = []
    error_count = 0
    error_details = []
    semaphore = asyncio.Semaphore(concurrency)

    transport = httpx.ASGITransport(app=app)
    proc = psutil.Process()
    mem_before = proc.memory_info().rss / (1024 * 1024)
    cpu_samples = []

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", follow_redirects=True) as client:
        async def worker():
            nonlocal error_count
            async with semaphore:
                t0 = time.perf_counter()
                try:
                    resp = await client.get(url, headers=headers, timeout=30.0)
                    duration_ms = (time.perf_counter() - t0) * 1000.0
                    if resp.status_code == 200:
                        latencies.append(duration_ms)
                    else:
                        error_count += 1
                        if len(error_details) < 5:
                            error_details.append(f"HTTP {resp.status_code}: {resp.text[:100]}")
                except Exception as ex:
                    error_count += 1
                    if len(error_details) < 5:
                        error_details.append(str(ex))

        t_start = time.perf_counter()
        tasks = [worker() for _ in range(total_requests)]
        await asyncio.gather(*tasks)
        total_time = time.perf_counter() - t_start

    mem_after = proc.memory_info().rss / (1024 * 1024)

    if not latencies:
        print(f"    [!] FAILED: 0 successful requests (Errors: {error_count})")
        return {
            "endpoint": endpoint_name,
            "concurrency": concurrency,
            "total_requests": total_requests,
            "successful": 0,
            "errors": error_count,
            "error_rate_pct": 100.0,
            "error_samples": error_details,
            "throughput_rps": 0.0
        }

    sorted_lats = sorted(latencies)
    p50 = statistics.median(sorted_lats)
    p90 = sorted_lats[int(len(sorted_lats) * 0.90)]
    p95 = sorted_lats[int(len(sorted_lats) * 0.95)]
    p99 = sorted_lats[min(int(len(sorted_lats) * 0.99), len(sorted_lats) - 1)]
    rps = len(latencies) / total_time if total_time > 0 else 0.0

    pool_max = settings.DB_POOL_SIZE + settings.DB_MAX_OVERFLOW
    pool_util = round(((engine.pool.checkedout() + max(0, engine.pool.overflow())) / max(1, pool_max)) * 100.0, 1)

    result = {
        "endpoint": endpoint_name,
        "concurrency": concurrency,
        "total_requests": total_requests,
        "successful": len(latencies),
        "errors": error_count,
        "error_rate_pct": round((error_count / total_requests) * 100.0, 2),
        "duration_sec": round(total_time, 3),
        "throughput_rps": round(rps, 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p90_ms": round(p90, 2),
        "latency_p95_ms": round(p95, 2),
        "latency_p99_ms": round(p99, 2),
        "latency_mean_ms": round(statistics.mean(sorted_lats), 2),
        "connection_wait_est_ms": round(max(0.0, p50 - 5.0), 2) if "DB" in endpoint_name else 0.0,
        "pool_utilization_pct": pool_util,
        "rss_memory_mb": round(mem_after, 2),
        "error_samples": error_details[:3]
    }

    print(f"    [+] Completed in {result['duration_sec']}s | Throughput: {result['throughput_rps']} req/s")
    print(f"    [+] P50: {result['latency_p50_ms']}ms | P95: {result['latency_p95_ms']}ms | P99: {result['latency_p99_ms']}ms")
    print(f"    [+] Errors: {result['errors']} ({result['error_rate_pct']}%) | RAM: {result['rss_memory_mb']} MB | Pool: {pool_util}%")
    return result


async def run_all_concurrency_tiers():
    token = seed_bench_user()
    tiers = [10, 25, 50, 100]
    all_results = []

    print("=================================================================")
    print("CONCURRENCY SCALING BENCHMARK: 10, 25, 50, 100 USERS")
    print("=================================================================")

    # Test 1: In-Memory / Lightweight (/health/live)
    print("\n--- BENCHMARK SUITE A: Liveness Probe (/health/live) ---")
    for c in tiers:
        # 4x concurrency requests per tier
        reqs = max(100, c * 5)
        res = await benchmark_concurrency_tier(
            endpoint_name="Liveness Probe",
            url="/health/live",
            token=token,
            concurrency=c,
            total_requests=reqs
        )
        all_results.append(res)

    # Test 2: Database-Backed Endpoint (/api/v1/auth/me)
    print("\n--- BENCHMARK SUITE B: Database-Backed Endpoint (/api/v1/auth/me) ---")
    for c in tiers:
        reqs = max(50, c * 3)
        res = await benchmark_concurrency_tier(
            endpoint_name="DB User Profile",
            url="/api/v1/auth/me",
            token=token,
            concurrency=c,
            total_requests=reqs
        )
        all_results.append(res)

    out_file = "PHASE_7_6_CONCURRENCY_RESULTS.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n[+] Results written to {out_file}")


if __name__ == "__main__":
    asyncio.run(run_all_concurrency_tiers())
