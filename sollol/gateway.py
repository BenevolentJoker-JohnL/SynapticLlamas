"""
FastAPI gateway with performance-aware routing, metrics, and autobatch integration.
"""
from fastapi import FastAPI, Request, HTTPException
import random
import asyncio
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from sollol.metrics import record_request, start_metrics_server
from sollol.autobatch import autobatch_loop
from sollol.memory import get_best_host, get_all_hosts_meta, health_check_all_hosts, queue_document
from sollol.adaptive_metrics import adaptive_metrics_loop
from sollol.intelligence import get_router

app = FastAPI(title="SOLLOL", description="Super Ollama Load Balancer")
_ray_actors = []
_dask_client = None

def start_api(
    ray_actors,
    dask_client,
    port=8000,
    enable_autobatch=True,
    autobatch_interval=60,
    enable_adaptive_metrics=True,
    adaptive_metrics_interval=30
):
    """
    Start FastAPI gateway with integrated metrics and autobatch.

    Args:
        ray_actors: List of Ray OllamaWorker actors
        dask_client: Dask distributed client
        port: Port to run the gateway on
        enable_autobatch: Whether to enable autonomous batch processing
        autobatch_interval: Seconds between autobatch cycles
        enable_adaptive_metrics: Whether to enable dynamic metrics feedback loop
        adaptive_metrics_interval: Seconds between adaptive metrics updates
    """
    global _ray_actors, _dask_client
    _ray_actors = ray_actors
    _dask_client = dask_client

    # Start Prometheus metrics server
    start_metrics_server(port=9090)

    # Start autobatch pipeline if enabled and Dask is available
    if enable_autobatch and _dask_client:
        asyncio.create_task(autobatch_loop(_dask_client, interval_sec=autobatch_interval))
        print(f"🛠️  Autobatch pipeline started (interval: {autobatch_interval}s)")
    elif enable_autobatch and not _dask_client:
        print(f"⚠️  Autobatch disabled (Dask not available)")

    # Start adaptive metrics feedback loop if enabled
    if enable_adaptive_metrics:
        asyncio.create_task(adaptive_metrics_loop(interval_sec=adaptive_metrics_interval))
        print(f"📊 Adaptive metrics loop started (interval: {adaptive_metrics_interval}s)")

    # Start periodic health checks
    asyncio.create_task(periodic_health_check())

    import uvicorn
    print(f"🌐 Starting FastAPI gateway on port {port}")
    print(f"   API docs: http://localhost:{port}/docs")
    uvicorn.run(app, host="0.0.0.0", port=port)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=2))
async def call_worker(worker, payload: dict, priority: int = 5):
    """
    Call Ray worker with INTELLIGENT routing based on request analysis.

    This uses the IntelligentRouter to:
    - Detect task type (generation, embedding, classification, etc.)
    - Estimate complexity and resource requirements
    - Select optimal node based on capabilities and current load
    - Provide routing decision reasoning for observability

    Args:
        worker: Ray OllamaWorker actor
        payload: Request payload
        priority: Request priority (1-10, higher = more important)

    Returns:
        Response from OLLOL host with routing metadata
    """
    router = get_router()

    # Analyze request to understand what it needs
    context = router.analyze_request(payload, priority=priority)

    # Get available hosts
    hosts_meta = get_all_hosts_meta()
    available = [h for h in hosts_meta if h.get('available', True)]

    if not available:
        raise HTTPException(status_code=503, detail="No available OLLOL hosts")

    # Intelligently select best host for this specific request
    selected_host, decision = router.select_optimal_node(context, available)

    # Log routing decision for observability
    print(f"🎯 Intelligent routing: {decision['reasoning']}")

    # Execute request on selected host
    import time
    start_time = time.time()

    result = await worker.chat.remote(payload, selected_host)

    # Record performance for learning
    duration_ms = (time.time() - start_time) * 1000
    router.record_performance(
        context.task_type,
        payload.get('model', 'unknown'),
        duration_ms
    )

    # Add routing metadata to response for transparency
    if isinstance(result, dict):
        result['_sollol_routing'] = {
            'host': selected_host,
            'task_type': context.task_type,
            'complexity': context.complexity,
            'decision_score': decision['score'],
            'actual_duration_ms': duration_ms,
        }

    return result

@app.post("/api/chat")
@record_request
async def chat_endpoint(request: Request, priority: int = 5):
    """
    Chat completion endpoint with INTELLIGENT routing.

    Features:
    - Automatic task type detection (generation, classification, etc.)
    - Context-aware node selection based on request complexity
    - Priority support (1-10, higher = more important)
    - Automatic failover if selected node fails
    - Routing decision transparency in response metadata

    Args:
        request: FastAPI request
        priority: Request priority (default: 5)

    Returns:
        Chat completion with routing metadata
    """
    payload = await request.json()

    if not _ray_actors:
        raise HTTPException(status_code=503, detail="No Ollama workers running")

    # Priority handling: higher priority requests get preference
    worker = random.choice(_ray_actors)

    # Attempt with intelligent routing and automatic failover
    max_attempts = 3
    last_error = None

    for attempt in range(max_attempts):
        try:
            result = await call_worker(worker, payload, priority=priority)
            return result
        except Exception as e:
            last_error = e
            print(f"⚠️  Attempt {attempt + 1}/{max_attempts} failed: {e}")

            # If we have more attempts, mark current best host as temporarily unavailable
            if attempt < max_attempts - 1:
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
                continue

    # All attempts failed
    raise HTTPException(
        status_code=503,
        detail=f"All routing attempts failed: {str(last_error)}"
    )

@app.post("/api/embed")
@record_request
async def embed_endpoint(request: Request):
    """
    Embedding endpoint (synchronous).
    """
    payload = await request.json()
    text = payload.get("text", "")
    model = payload.get("model", "nomic-embed-text")

    if not _ray_actors:
        raise HTTPException(status_code=503, detail="No Ollama workers running")

    host = get_best_host(task_type="embedding")
    if not host:
        raise HTTPException(status_code=503, detail="No available OLLOL hosts")

    worker = random.choice(_ray_actors)

    try:
        result = await worker.embed.remote(text, host, model)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/embed/batch")
@record_request
async def embed_batch_endpoint(request: Request):
    """
    Queue documents for batch embedding via Dask autobatch pipeline.
    """
    payload = await request.json()
    docs = payload.get("docs", [])

    if not docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    if not _dask_client:
        raise HTTPException(status_code=503, detail="Dask not running")

    # Queue documents for autobatch processing
    for doc in docs:
        queue_document(doc)

    return {
        "status": "queued",
        "count": len(docs),
        "message": "Documents queued for batch embedding"
    }

@app.get("/api/health")
async def health_check():
    """
    Check health of SOLLOL gateway and OLLOL hosts.
    """
    host_health = await health_check_all_hosts()

    return {
        "status": "healthy",
        "ray_workers": len(_ray_actors),
        "dask_available": _dask_client is not None,
        "hosts": host_health,
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/stats")
def stats_endpoint():
    """
    Get comprehensive performance statistics and routing intelligence.

    Returns detailed metrics about:
    - Host performance and availability
    - Routing decisions and patterns
    - Task type distribution
    - Performance history
    """
    hosts_meta = get_all_hosts_meta()
    router = get_router()

    return {
        "hosts": [
            {
                "host": meta["host"],
                "available": meta["available"],
                "latency_ms": meta["latency_ms"],
                "success_rate": meta["success_rate"],
                "cpu_load": meta["cpu_load"],
                "gpu_free_mem": meta["gpu_free_mem"],
                "priority": meta["priority"],
                "last_updated": meta["last_updated"].isoformat()
            }
            for meta in hosts_meta
        ],
        "routing_intelligence": {
            "task_patterns_detected": list(router.task_patterns.keys()),
            "performance_history_tasks": len(router.performance_history),
            "learned_patterns": {
                task_model: {
                    "samples": len(durations),
                    "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
                    "min_duration_ms": min(durations) if durations else 0,
                    "max_duration_ms": max(durations) if durations else 0,
                }
                for task_model, durations in router.performance_history.items()
            }
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/dashboard")
async def dashboard_endpoint():
    """
    Get real-time dashboard data for observability.

    This endpoint provides everything needed for a monitoring dashboard:
    - Current system status
    - Routing decisions and reasoning
    - Performance metrics
    - Resource utilization
    - Alert conditions
    """
    hosts_meta = get_all_hosts_meta()
    router = get_router()

    # Calculate aggregate metrics
    available_hosts = [h for h in hosts_meta if h['available']]
    avg_latency = sum(h['latency_ms'] for h in available_hosts) / len(available_hosts) if available_hosts else 0
    avg_success_rate = sum(h['success_rate'] for h in available_hosts) / len(available_hosts) if available_hosts else 0
    total_gpu_mem = sum(h['gpu_free_mem'] for h in available_hosts)

    # Detect alert conditions
    alerts = []
    for host in hosts_meta:
        if not host['available']:
            alerts.append({
                "severity": "error",
                "message": f"Host {host['host']} is unavailable",
                "timestamp": datetime.now().isoformat()
            })
        elif host['success_rate'] < 0.8:
            alerts.append({
                "severity": "warning",
                "message": f"Host {host['host']} has low success rate: {host['success_rate']:.1%}",
                "timestamp": datetime.now().isoformat()
            })
        elif host['latency_ms'] > 1000:
            alerts.append({
                "severity": "warning",
                "message": f"Host {host['host']} has high latency: {host['latency_ms']:.0f}ms",
                "timestamp": datetime.now().isoformat()
            })

    return {
        "status": {
            "healthy": len(alerts) == 0,
            "total_hosts": len(hosts_meta),
            "available_hosts": len(available_hosts),
            "ray_workers": len(_ray_actors),
            "dask_available": _dask_client is not None,
        },
        "performance": {
            "avg_latency_ms": avg_latency,
            "avg_success_rate": avg_success_rate,
            "total_gpu_memory_mb": total_gpu_mem,
        },
        "routing": {
            "intelligent_routing_enabled": True,
            "task_types_learned": len(router.performance_history),
            "patterns_available": list(router.task_patterns.keys()),
        },
        "alerts": alerts,
        "hosts": [
            {
                "host": h["host"],
                "status": "healthy" if h["available"] and h["success_rate"] > 0.8 else "degraded",
                "latency_ms": h["latency_ms"],
                "success_rate": h["success_rate"],
                "load": h["cpu_load"],
                "gpu_mb": h["gpu_free_mem"],
            }
            for h in hosts_meta
        ],
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/batch-status")
def batch_status():
    """
    Get Dask batch processing status.
    """
    if _dask_client:
        try:
            scheduler_info = _dask_client.scheduler_info()
            return {
                "status": "running",
                "n_tasks": len(scheduler_info.get("tasks", {})),
                "n_workers": len(scheduler_info.get("workers", {})),
            }
        except Exception as e:
            return {"error": f"Could not get Dask status: {e}"}
    return {"status": "Dask not running"}

async def periodic_health_check(interval_sec: int = 120):
    """
    Periodically check health of all OLLOL hosts.

    Args:
        interval_sec: Seconds between health checks
    """
    while True:
        try:
            await asyncio.sleep(interval_sec)
            await health_check_all_hosts()
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Health check completed")
        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⚠️  Health check error: {e}")
