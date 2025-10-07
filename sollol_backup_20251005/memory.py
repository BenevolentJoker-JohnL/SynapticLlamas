"""
Memory layer for SOLLOL - host management and performance-aware routing.
"""
import os
import asyncio
import httpx
from typing import List, Dict, Optional
from datetime import datetime

HOSTS_FILE = "config/hosts.txt"

# Host metadata with performance metrics
# Will be dynamically updated by metrics feedback loop
HOSTS_META = []

def load_hosts_from_file(hosts_file: str = HOSTS_FILE) -> List[str]:
    """Load OLLOL hosts from configuration file."""
    if not os.path.exists(hosts_file):
        print(f"⚠️  Host file not found: {hosts_file}")
        return []

    with open(hosts_file) as f:
        hosts = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    return hosts

def init_hosts_meta(hosts: List[str]) -> None:
    """Initialize HOSTS_META with default values for each host."""
    global HOSTS_META
    HOSTS_META = [
        {
            "host": host,
            "cpu_load": 0.5,  # Default unknown load
            "gpu_free_mem": 8000,  # Default 8GB free
            "priority": idx,  # Lower priority = preferred
            "latency_ms": 0.0,
            "success_rate": 1.0,
            "last_updated": datetime.now(),
            "available": True,
        }
        for idx, host in enumerate(hosts)
    ]
    print(f"✅ Initialized metadata for {len(HOSTS_META)} hosts")

def get_hosts() -> List[str]:
    """Return list of all configured hosts."""
    return [meta["host"] for meta in HOSTS_META if meta["available"]]

def get_all_hosts_meta() -> List[Dict]:
    """Return full metadata for all hosts."""
    return HOSTS_META

def get_best_host(task_type: str = "default") -> Optional[str]:
    """
    Return OLLOL host with optimal resources based on performance metrics.

    Scoring formula:
    - Lower score = better host
    - Factors: CPU load, GPU memory, priority, latency, success rate
    """
    available_hosts = [h for h in HOSTS_META if h["available"]]

    if not available_hosts:
        print("⚠️  No available hosts found")
        return None

    def score(host: Dict) -> float:
        # Weighted scoring - lower is better
        cpu_score = host["cpu_load"] * 0.3
        gpu_score = (1 / (host["gpu_free_mem"] + 1)) * 0.2
        priority_score = host["priority"] * 0.1
        latency_score = (host["latency_ms"] / 1000.0) * 0.2
        reliability_score = (1.0 - host["success_rate"]) * 0.2

        return cpu_score + gpu_score + priority_score + latency_score + reliability_score

    best_host = min(available_hosts, key=score)
    return best_host["host"]

def update_host_metrics(host: str, metrics: Dict) -> None:
    """
    Update performance metrics for a specific host.

    Args:
        host: Host address (e.g., "10.0.0.2:11434")
        metrics: Dict containing any of: cpu_load, gpu_free_mem, latency_ms, success_rate
    """
    for host_meta in HOSTS_META:
        if host_meta["host"] == host:
            host_meta.update(metrics)
            host_meta["last_updated"] = datetime.now()
            break

def mark_host_unavailable(host: str) -> None:
    """Mark a host as unavailable after failures."""
    for host_meta in HOSTS_META:
        if host_meta["host"] == host:
            host_meta["available"] = False
            host_meta["last_updated"] = datetime.now()
            print(f"❌ Marked {host} as unavailable")
            break

def mark_host_available(host: str) -> None:
    """Mark a host as available."""
    for host_meta in HOSTS_META:
        if host_meta["host"] == host:
            host_meta["available"] = True
            host_meta["last_updated"] = datetime.now()
            print(f"✅ Marked {host} as available")
            break

async def health_check_host(host: str) -> bool:
    """
    Check if an OLLOL host is responsive.

    Returns:
        True if host is healthy, False otherwise
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"http://{host}/api/tags")
            return resp.status_code == 200
    except Exception as e:
        print(f"⚠️  Health check failed for {host}: {e}")
        return False

async def health_check_all_hosts() -> Dict[str, bool]:
    """
    Run health checks on all configured hosts.

    Returns:
        Dict mapping host to health status
    """
    tasks = []
    hosts = get_hosts()

    for host in [meta["host"] for meta in HOSTS_META]:
        tasks.append(health_check_host(host))

    results = await asyncio.gather(*tasks)

    health_status = {}
    for host_meta, is_healthy in zip(HOSTS_META, results):
        host = host_meta["host"]
        health_status[host] = is_healthy

        if is_healthy:
            mark_host_available(host)
        else:
            mark_host_unavailable(host)

    return health_status

# Placeholder for document queue (for autobatch)
_document_queue = []
_last_doc_id = 0

def fetch_new_docs() -> List[str]:
    """
    Fetch new documents that need embedding.

    In production, this would poll a database or message queue.
    For now, it's a simple placeholder that generates sample docs.
    """
    global _last_doc_id, _document_queue

    # Return queued docs if any
    if _document_queue:
        docs = _document_queue.copy()
        _document_queue.clear()
        return docs

    # Generate sample docs (for testing)
    # In production, replace with actual data source
    return []

def queue_document(doc: str) -> None:
    """Add a document to the embedding queue."""
    _document_queue.append(doc)
