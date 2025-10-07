"""
Prometheus metrics collection and monitoring for SOLLOL.
"""
import time
import asyncio
from functools import wraps
from typing import Callable, Dict
from datetime import datetime
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from sollol.memory import update_host_metrics

# Prometheus metrics
REQUEST_COUNT = Counter(
    'sollol_requests_total',
    'Total number of requests processed',
    ['endpoint', 'status']
)

REQUEST_LATENCY = Histogram(
    'sollol_request_latency_seconds',
    'Request latency in seconds',
    ['endpoint']
)

WORKER_FAILURES = Counter(
    'sollol_worker_failures_total',
    'Total number of worker failures',
    ['host']
)

ACTIVE_REQUESTS = Gauge(
    'sollol_active_requests',
    'Number of requests currently being processed'
)

HOST_LATENCY = Gauge(
    'sollol_host_latency_ms',
    'Average latency per host in milliseconds',
    ['host']
)

HOST_SUCCESS_RATE = Gauge(
    'sollol_host_success_rate',
    'Success rate per host (0.0 to 1.0)',
    ['host']
)

# In-memory metrics for routing decisions
_host_stats: Dict[str, Dict] = {}

def init_host_stats(hosts: list):
    """Initialize tracking for each host."""
    global _host_stats
    for host in hosts:
        _host_stats[host] = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_latency_ms": 0.0,
            "success_rate": 1.0,
            "avg_latency_ms": 0.0,
        }

def record_request_decorator(func: Callable):
    """
    Decorator to record request metrics for FastAPI endpoints.
    Tracks latency, status, and updates Prometheus metrics.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        endpoint = func.__name__
        start_time = time.time()
        ACTIVE_REQUESTS.inc()

        status = "success"
        try:
            result = await func(*args, **kwargs)
            return result
        except Exception as e:
            status = "error"
            raise e
        finally:
            latency = time.time() - start_time
            REQUEST_COUNT.labels(endpoint=endpoint, status=status).inc()
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(latency)
            ACTIVE_REQUESTS.dec()

    return wrapper

# Alias for convenience
record_request = record_request_decorator

def record_host_request(host: str, latency_ms: float, success: bool):
    """
    Record metrics for a request to a specific OLLOL host.

    Args:
        host: OLLOL host address
        latency_ms: Request latency in milliseconds
        success: Whether the request succeeded
    """
    if host not in _host_stats:
        _host_stats[host] = {
            "total_requests": 0,
            "failed_requests": 0,
            "total_latency_ms": 0.0,
            "success_rate": 1.0,
            "avg_latency_ms": 0.0,
        }

    stats = _host_stats[host]
    stats["total_requests"] += 1
    stats["total_latency_ms"] += latency_ms

    if not success:
        stats["failed_requests"] += 1
        WORKER_FAILURES.labels(host=host).inc()

    # Calculate running averages
    stats["avg_latency_ms"] = stats["total_latency_ms"] / stats["total_requests"]
    stats["success_rate"] = (
        (stats["total_requests"] - stats["failed_requests"]) / stats["total_requests"]
    )

    # Update Prometheus gauges
    HOST_LATENCY.labels(host=host).set(stats["avg_latency_ms"])
    HOST_SUCCESS_RATE.labels(host=host).set(stats["success_rate"])

    # Update memory layer for routing decisions
    update_host_metrics(
        host,
        {
            "latency_ms": stats["avg_latency_ms"],
            "success_rate": stats["success_rate"],
        }
    )

def get_host_stats(host: str) -> Dict:
    """Get current statistics for a specific host."""
    return _host_stats.get(host, {})

def get_all_host_stats() -> Dict[str, Dict]:
    """Get statistics for all hosts."""
    return _host_stats

def start_metrics_server(port: int = 9090):
    """
    Start Prometheus metrics HTTP server.

    Args:
        port: Port to expose metrics on (default: 9090)
    """
    try:
        start_http_server(port)
        print(f"📊 Prometheus metrics server started on port {port}")
        print(f"   View metrics at: http://localhost:{port}/metrics")
    except Exception as e:
        print(f"⚠️  Failed to start metrics server: {e}")

async def collect_system_metrics_loop(interval_sec: int = 30):
    """
    Periodically collect system-level metrics.

    In production, this would query actual CPU/GPU/memory from each host.
    For now, it's a placeholder for future implementation.
    """
    while True:
        try:
            # TODO: Implement actual system metrics collection
            # - Query CPU load from each OLLOL host
            # - Query GPU memory from each OLLOL host
            # - Update HOSTS_META accordingly
            pass
        except Exception as e:
            print(f"⚠️  Error collecting system metrics: {e}")

        await asyncio.sleep(interval_sec)
