"""
Dynamic metrics feedback loop for adaptive routing.
Automatically updates host performance metadata based on real-time system metrics.
"""
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Optional
from sollol.memory import update_host_metrics, get_all_hosts_meta, HOSTS_META

async def fetch_host_system_metrics(host: str) -> Optional[Dict]:
    """
    Fetch real-time system metrics from an OLLOL host.

    This function attempts to get system information from Ollama's API.
    In production, you might integrate with:
    - Prometheus node_exporter
    - Custom OLLOL /metrics endpoint
    - System monitoring tools (telegraf, collectd, etc.)

    Args:
        host: OLLOL host address

    Returns:
        Dict with system metrics or None if unavailable
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to get model info which contains some system data
            resp = await client.get(f"http://{host}/api/tags")

            if resp.status_code != 200:
                return None

            # For now, we'll use response time as a proxy for system load
            # In production, you'd query actual metrics endpoints
            latency_ms = resp.elapsed.total_seconds() * 1000

            # Placeholder for actual system metrics
            # TODO: Integrate with real metrics sources
            return {
                "latency_ms": latency_ms,
                "available": True,
                # These would come from actual monitoring in production:
                # "cpu_load": cpu_percent,
                # "gpu_free_mem": gpu_memory_free,
            }

    except Exception as e:
        print(f"⚠️  Failed to fetch metrics from {host}: {e}")
        return None

async def update_host_from_system_metrics(host: str):
    """
    Fetch and update metrics for a single host.

    Args:
        host: OLLOL host address
    """
    metrics = await fetch_host_system_metrics(host)

    if metrics:
        update_host_metrics(host, metrics)
        print(
            f"[{datetime.now().strftime('%H:%M:%S')}] "
            f"📊 Updated metrics for {host}: "
            f"latency={metrics.get('latency_ms', 0):.1f}ms"
        )
    else:
        # Mark host as potentially unavailable
        update_host_metrics(host, {"available": False})

async def adaptive_metrics_loop(interval_sec: int = 30):
    """
    Continuous loop that updates host metrics based on real-time system data.

    This creates a feedback loop where:
    1. System metrics are collected from all hosts
    2. Host metadata is updated with fresh performance data
    3. Routing decisions use the latest metrics automatically

    Args:
        interval_sec: Seconds between metric collection cycles
    """
    print(f"🔄 Adaptive metrics loop started (interval: {interval_sec}s)")

    while True:
        try:
            # Get all configured hosts
            hosts_meta = get_all_hosts_meta()

            if not hosts_meta:
                print("⚠️  No hosts configured for adaptive metrics")
                await asyncio.sleep(interval_sec)
                continue

            # Fetch metrics from all hosts concurrently
            tasks = [
                update_host_from_system_metrics(meta["host"])
                for meta in hosts_meta
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"✅ Adaptive metrics updated for {len(hosts_meta)} hosts"
            )

        except Exception as e:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] "
                f"❌ Adaptive metrics error: {e}"
            )

        await asyncio.sleep(interval_sec)

# Integration with Prometheus node_exporter (optional)
async def fetch_prometheus_node_metrics(host: str, prometheus_port: int = 9100) -> Optional[Dict]:
    """
    Fetch system metrics from Prometheus node_exporter.

    This provides much richer system metrics than Ollama's API alone.

    Args:
        host: OLLOL host address (just the hostname, without :11434)
        prometheus_port: Port where node_exporter is running

    Returns:
        Dict with parsed metrics or None
    """
    # Extract hostname from host:port format
    hostname = host.split(":")[0]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://{hostname}:{prometheus_port}/metrics")

            if resp.status_code != 200:
                return None

            # Parse Prometheus metrics (simplified)
            # In production, use prometheus_client or proper parser
            text = resp.text
            metrics = {}

            for line in text.split("\n"):
                if line.startswith("node_cpu_seconds_total"):
                    # Parse CPU usage
                    pass
                elif line.startswith("node_memory_MemAvailable_bytes"):
                    # Parse memory
                    pass
                # Add GPU metrics parsing if available (nvidia_smi_exporter)

            return metrics

    except Exception as e:
        print(f"⚠️  Failed to fetch Prometheus metrics from {hostname}:{prometheus_port}: {e}")
        return None
