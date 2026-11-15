import threading
import time
from typing import Dict, List, Optional, Tuple


class MetricValue:
    """Thread-safe metric value container with labels."""

    def __init__(self, name: str, doc: str, metric_type: str):
        self.name = name
        self.doc = doc
        self.metric_type = metric_type
        self._lock = threading.Lock()
        self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

    def _labels_key(self, labels: Optional[Dict[str, str]] = None) -> Tuple[Tuple[str, str], ...]:
        if not labels:
            return ()
        return tuple(sorted(labels.items()))

    def inc(self, amount: float = 1.0, labels: Optional[Dict[str, str]] = None):
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] = self._values.get(key, 0.0) + amount

    def set(self, value: float, labels: Optional[Dict[str, str]] = None):
        key = self._labels_key(labels)
        with self._lock:
            self._values[key] = value

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None):
        # Stores sum and count for summary metrics
        self.inc(amount=value, labels={**(labels or {}), "_stat": "sum"})
        self.inc(amount=1.0, labels={**(labels or {}), "_stat": "count"})

    def format_prometheus(self) -> str:
        lines = [
            f"# HELP {self.name} {self.doc}",
            f"# TYPE {self.name} {self.metric_type}"
        ]
        with self._lock:
            for label_tuple, val in self._values.items():
                if label_tuple:
                    label_str = ",".join(f'{k}="{v}"' for k, v in label_tuple)
                    lines.append(f"{self.name}{{{label_str}}} {val}")
                else:
                    lines.append(f"{self.name} {val}")
        return "\n".join(lines)


class PrometheusRegistry:
    """Enterprise Prometheus metrics registry with zero external runtime dependencies."""

    def __init__(self):
        self._metrics: Dict[str, MetricValue] = {}
        self._lock = threading.Lock()
        self._init_core_metrics()

    def _init_core_metrics(self):
        self.register("fintrust_http_requests_total", "Total count of HTTP requests", "counter")
        self.register("fintrust_http_request_duration_seconds", "HTTP request latency in seconds", "summary")
        self.register("fintrust_db_pool_checked_in", "Active database connections currently checked in to pool", "gauge")
        self.register("fintrust_db_pool_checked_out", "Active database connections currently checked out of pool", "gauge")
        self.register("fintrust_rag_queries_total", "Total RAG queries executed", "counter")
        self.register("fintrust_rag_retrieval_duration_seconds", "Retrieval and fusion latency in seconds", "summary")
        self.register("fintrust_agent_executions_total", "Total agent workflow executions", "counter")
        self.register("fintrust_rate_limit_hits_total", "Total requests rejected due to rate limiting", "counter")
        self.register("fintrust_token_usage_total", "Estimated LLM tokens consumed", "counter")

    def register(self, name: str, doc: str, metric_type: str) -> MetricValue:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = MetricValue(name, doc, metric_type)
            return self._metrics[name]

    def get(self, name: str) -> MetricValue:
        return self._metrics[name]

    def generate_exposition(self) -> str:
        with self._lock:
            metrics_list = list(self._metrics.values())
        blocks = [m.format_prometheus() for m in metrics_list]
        return "\n\n".join(blocks) + "\n"


# Global Prometheus metrics registry singleton
metrics_registry = PrometheusRegistry()
