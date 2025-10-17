"""
SOLLOL Dashboard Server for SynapticLlamas

Serves the SOLLOL monitoring dashboard and provides real-time updates
via WebSockets for load balancer statistics and centralized logging.
"""
import json
import logging
import queue
import requests
import time
from datetime import datetime
from logging import Handler

from flask import Flask, jsonify, send_file
from flask_cors import CORS
from flask_sock import Sock

# Import Redis log publisher
try:
    from redis_log_publisher import RedisLogPublisher, ComponentType, LogLevel, get_global_publisher
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis_log_publisher not available - Redis logging disabled")

# Centralized logging queue
log_queue = queue.Queue()

class QueueLogHandler(Handler):
    """Custom logging handler to push logs into a queue."""
    def __init__(self, log_queue):
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record):
        log_entry = self.format(record)
        self.log_queue.put(log_entry)

# Aggressively take over the logging configuration
root_logger = logging.getLogger()
if root_logger.hasHandlers():
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

log_handler = QueueLogHandler(log_queue)
log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_formatter)

root_logger.addHandler(log_handler)
root_logger.setLevel(logging.INFO)

# Specifically hijack the werkzeug logger
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.handlers = []
werkzeug_logger.addHandler(log_handler)
werkzeug_logger.propagate = False # Prevent duplicate logs

logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
sock = Sock(app)

# Global references
registry = None
load_balancer = None
hybrid_router = None  # For llama.cpp monitoring
rpc_backend_registry = None  # For RPC backend monitoring
redis_publisher = None  # For Redis log publishing

def get_dashboard_data():
    """Get comprehensive dashboard data."""
    if not registry:
        logger.warning("Dashboard: No registry available")
        return {}

    if not load_balancer:
        logger.warning("Dashboard: No load_balancer available")
        return {}

    logger.debug(f"📊 [DASHBOARD DEBUG] Registry object ID: {id(registry)}")
    logger.debug(f"📊 [DASHBOARD DEBUG] Registry nodes: {list(registry.nodes.keys())}")

    stats = load_balancer.get_stats()
    healthy_nodes = registry.get_healthy_nodes()

    # Debug logging
    logger.debug(f"Dashboard: Registry has {len(registry.nodes)} nodes")
    logger.debug(f"Dashboard: registry.nodes type = {type(registry.nodes)}")

    all_nodes = list(registry.nodes.values()) if isinstance(registry.nodes, dict) else registry.nodes if isinstance(registry.nodes, list) else []
    logger.debug(f"Dashboard: all_nodes count = {len(all_nodes)}")

    total_requests = sum(getattr(n.metrics, 'total_requests', 0) for n in all_nodes if hasattr(n, 'metrics'))
    successful_requests = sum(getattr(n.metrics, 'successful_requests', 0) for n in all_nodes if hasattr(n, 'metrics'))
    avg_success_rate = successful_requests / total_requests if total_requests > 0 else 1.0

    avg_latency = (sum(getattr(n.metrics, 'avg_latency', 0) for n in healthy_nodes if hasattr(n, 'metrics')) / len(healthy_nodes)) if healthy_nodes else 0
    total_gpu_memory = sum(getattr(n.capabilities, 'gpu_memory_mb', 0) for n in all_nodes if hasattr(n, 'capabilities') and getattr(n.capabilities, 'has_gpu', False))

    hosts = []
    for node in all_nodes:
        url = getattr(node, 'url', str(node))
        is_healthy = getattr(node, 'is_healthy', True)

        metrics = getattr(node, 'metrics', None)
        avg_latency_node = getattr(metrics, 'avg_latency', 0.0) if metrics else 0.0
        total_reqs = getattr(metrics, 'total_requests', 0) if metrics else 0
        successful_reqs = getattr(metrics, 'successful_requests', 0) if metrics else 0
        success_rate = successful_reqs / total_reqs if total_reqs > 0 else 1.0

        logger.debug(
            f"📊 [DASHBOARD DEBUG] Node {url}: "
            f"total_requests={total_reqs}, avg_latency={avg_latency_node:.0f}ms, "
            f"object_id={id(node)}"
        )

        load_score = 0.5
        if hasattr(node, 'calculate_load_score'):
            try:
                load_score = node.calculate_load_score() / 100.0
            except Exception:
                load_score = 0.5
        
        gpu_mb = getattr(getattr(node, 'capabilities', None), 'gpu_memory_mb', 0)

        host_data = {
            'host': url,
            'status': 'healthy' if is_healthy else 'offline',
            'latency_ms': avg_latency_node,
            'success_rate': success_rate,
            'load': load_score,
            'gpu_mb': gpu_mb,
        }
        if is_healthy and (avg_latency_node > 1000 or success_rate < 0.9):
            host_data['status'] = 'degraded'
        hosts.append(host_data)

    alerts = []
    for node in all_nodes:
        if not getattr(node, 'is_healthy', True):
            alerts.append({
                'severity': 'error',
                'message': f'Node {getattr(node, "url", "N/A")} is offline',
                'timestamp': getattr(node, 'last_health_check', datetime.now()).isoformat()
            })
        elif hasattr(node, 'metrics') and getattr(node.metrics, 'avg_latency', 0) > 1000:
            alerts.append({
                'severity': 'warning',
                'message': f'High latency on {getattr(node, "url", "N/A")}: {node.metrics.avg_latency:.0f}ms',
                'timestamp': datetime.now().isoformat()
            })

    routing_patterns = []
    task_types_learned = 0
    if hasattr(load_balancer.metrics, 'get_summary'):
        summary = load_balancer.metrics.get_summary()
        if 'task_types' in summary:
            routing_patterns = list(summary['task_types'].keys())
            task_types_learned = len(routing_patterns)

    # Get RPC backend data from rpc_backend_registry (or fallback to hybrid_router)
    rpc_hosts = []
    registry_to_use = rpc_backend_registry

    # Fallback to hybrid_router if direct registry not available
    if not registry_to_use and hybrid_router and hasattr(hybrid_router, 'rpc_registry'):
        registry_to_use = hybrid_router.rpc_registry

    if registry_to_use and hasattr(registry_to_use, 'backends'):
        for addr, backend in registry_to_use.backends.items():
            rpc_host_data = {
                'host': backend.address,
                'status': 'healthy' if backend.is_healthy else 'offline',
                'total_requests': backend.metrics.total_requests,
                'total_failures': backend.metrics.total_failures,
                'success_rate': backend.metrics.success_rate,
                'avg_latency_ms': backend.metrics.avg_latency,
                'last_check': backend.metrics.last_health_check
            }
            rpc_hosts.append(rpc_host_data)

    return {
        'status': {'healthy': bool(healthy_nodes), 'available_hosts': len(healthy_nodes), 'total_hosts': len(all_nodes), 'ray_workers': 0},
        'performance': {'avg_latency_ms': avg_latency, 'avg_success_rate': avg_success_rate, 'total_gpu_memory_mb': total_gpu_memory},
        'hosts': hosts,
        'rpc_hosts': rpc_hosts,  # Add RPC backends data
        'alerts': alerts,
        'routing': {'patterns_available': routing_patterns, 'task_types_learned': task_types_learned},
    }

@app.route('/')
def index():
    """Serve the dashboard HTML."""
    return send_file('dashboard.html')

@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'sollol-dashboard'})

@app.route('/api/dashboard')
def api_dashboard():
    """HTTP endpoint for dashboard data (for debugging)."""
    data = get_dashboard_data()
    return jsonify(data)

@app.route('/api/debug/nodes')
def api_debug_nodes():
    """Debug endpoint showing raw node state."""
    if not registry:
        return jsonify({'error': 'No registry'})

    nodes_debug = []
    for url, node in registry.nodes.items():
        nodes_debug.append({
            'url': url,
            'node_object_id': id(node),
            'metrics': {
                'total_requests': node.metrics.total_requests,
                'failed_requests': node.metrics.failed_requests,
                'successful_requests': node.metrics.successful_requests,
                'avg_response_time': node.metrics.avg_response_time,
                'avg_latency': node.metrics.avg_latency,
            },
            'is_healthy': node.is_healthy,
            'load_score': node.calculate_load_score(),
        })

    return jsonify({'nodes': nodes_debug, 'registry_id': id(registry)})

@sock.route('/ws/dashboard')
def ws_dashboard(ws):
    """WebSocket endpoint for streaming dashboard data."""
    logger.info("Dashboard WebSocket client connected.")
    while True:
        data = get_dashboard_data()
        try:
            ws.send(json.dumps(data))
        except Exception as e:
            logger.warning(f"Dashboard WebSocket client disconnected: {e}")
            break
        time.sleep(30)  # Update every 30 seconds (reduced from 10s)

@sock.route('/ws/logs')
def ws_logs(ws):
    """WebSocket endpoint for streaming logs."""
    logger.info("Log streaming WebSocket client connected.")
    while True:
        try:
            log_entry = log_queue.get(timeout=1)
            ws.send(log_entry)
        except queue.Empty:
            continue
        except Exception as e:
            logger.warning(f"Log streaming WebSocket client disconnected: {e}")
            break

@sock.route('/ws/ollama_logs')
def ws_ollama_logs(ws):
    """
    WebSocket endpoint for streaming Ollama node activity.

    NOTE: This is a LEGACY endpoint that should NOT be doing its own polling.
    SynapticLlamas should report events to SOLLOL dashboard instead.

    This endpoint is kept for backward compatibility but should be deprecated.
    Use SOLLOL unified dashboard for monitoring instead.
    """
    logger.warning("ws_ollama_logs is deprecated - use SOLLOL unified dashboard instead")

    # Send deprecation message
    try:
        deprecation_msg = {
            'timestamp': time.time(),
            'node': 'system',
            'type': 'warning',
            'message': '⚠️  This monitoring endpoint is deprecated. Use SOLLOL unified dashboard at port 8080',
            'level': 'warning'
        }
        ws.send(json.dumps(deprecation_msg))
    except Exception as e:
        logger.error(f"Failed to send message: {e}")
        return

    # Keep connection alive but don't poll
    try:
        while True:
            time.sleep(60)  # Just keep connection alive, no polling
    except Exception:
        pass

@sock.route('/ws/llama_cpp_logs')
def ws_llama_cpp_logs(ws):
    """
    WebSocket endpoint for streaming llama.cpp coordinator and RPC backend activity.

    EVENT-DRIVEN: Only reports state changes, does not poll.
    Uses Redis pub/sub for real-time events when available.
    """
    logger.info("llama.cpp logs WebSocket client connected.")

    # Send initial connection message
    try:
        init_msg = {
            'timestamp': time.time(),
            'component': 'system',
            'type': 'info',
            'message': '🔌 Connected to llama.cpp monitoring',
            'level': 'info'
        }
        ws.send(json.dumps(init_msg))
    except Exception as e:
        logger.error(f"Failed to send init message: {e}")

    # Track previous state
    previous_state = {
        'coordinator_running': False,
        'coordinator_model': None,
        'rpc_backends': set(),
        'last_heartbeat': 0
    }

    while True:
        try:
            logs = []

            # Check if we have a hybrid router to monitor
            if not hybrid_router:
                # Send status update less frequently
                current_time = time.time()
                if current_time - previous_state['last_heartbeat'] >= 30:
                    status_msg = {
                        'timestamp': time.time(),
                        'component': 'system',
                        'type': 'info',
                        'message': '📡 No hybrid router configured (Ollama-only mode)',
                        'level': 'info'
                    }
                    ws.send(json.dumps(status_msg))
                    previous_state['last_heartbeat'] = current_time
                time.sleep(5)
                continue

            # Check coordinator status
            coordinator = getattr(hybrid_router, 'coordinator', None)
            coordinator_model = getattr(hybrid_router, 'coordinator_model', None)
            rpc_backends = getattr(hybrid_router, 'rpc_backends', None)
            enable_distributed = getattr(hybrid_router, 'enable_distributed', False)

            # Detect coordinator start
            if coordinator and not previous_state['coordinator_running']:
                model_path = getattr(coordinator, 'model_path', 'unknown')
                port = getattr(coordinator, 'port', 'unknown')
                log_entry = {
                    'timestamp': time.time(),
                    'component': 'coordinator',
                    'type': 'start',
                    'message': f"🚀 llama.cpp coordinator started (port {port})",
                    'level': 'info',
                    'details': {
                        'model_path': model_path,
                        'port': port
                    }
                }
                logs.append(json.dumps(log_entry))
                previous_state['coordinator_running'] = True

                # Publish to Redis
                if redis_publisher:
                    redis_publisher.publish_log(
                        component=ComponentType.COORDINATOR,
                        level=LogLevel.INFO,
                        message=f"llama.cpp coordinator started (port {port})",
                        event_type="start",
                        details={'model_path': model_path, 'port': port}
                    )

            # Detect coordinator stop
            if not coordinator and previous_state['coordinator_running']:
                log_entry = {
                    'timestamp': time.time(),
                    'component': 'coordinator',
                    'type': 'stop',
                    'message': '⏹️  llama.cpp coordinator stopped',
                    'level': 'warning'
                }
                logs.append(json.dumps(log_entry))
                previous_state['coordinator_running'] = False

                # Publish to Redis
                if redis_publisher:
                    redis_publisher.publish_coordinator_stop()

            # Detect model loading in coordinator
            if coordinator_model != previous_state['coordinator_model']:
                if coordinator_model:
                    log_entry = {
                        'timestamp': time.time(),
                        'component': 'coordinator',
                        'type': 'model_load',
                        'message': f"📦 Model loaded: {coordinator_model}",
                        'level': 'info',
                        'details': {'model': coordinator_model}
                    }
                    logs.append(json.dumps(log_entry))

                    # Publish to Redis
                    if redis_publisher:
                        redis_publisher.publish_model_load(
                            model_name=coordinator_model,
                            model_path=getattr(coordinator, 'model_path', 'unknown')
                        )
                previous_state['coordinator_model'] = coordinator_model

            # Monitor RPC backends
            if rpc_backends:
                current_backends = set()
                for backend_config in rpc_backends:
                    host = backend_config.get('host', 'unknown')
                    port = backend_config.get('port', 50052)
                    backend_addr = f"{host}:{port}"
                    current_backends.add(backend_addr)

                    # Detect new RPC backend
                    if backend_addr not in previous_state['rpc_backends']:
                        log_entry = {
                            'timestamp': time.time(),
                            'component': 'rpc_backend',
                            'type': 'connect',
                            'message': f"🔗 RPC backend connected: {backend_addr}",
                            'level': 'info',
                            'details': {'backend': backend_addr}
                        }
                        logs.append(json.dumps(log_entry))

                        # Publish to Redis
                        if redis_publisher:
                            redis_publisher.publish_rpc_backend_connect(backend_addr)

                # Detect removed RPC backends
                removed_backends = previous_state['rpc_backends'] - current_backends
                for backend_addr in removed_backends:
                    log_entry = {
                        'timestamp': time.time(),
                        'component': 'rpc_backend',
                        'type': 'disconnect',
                        'message': f"🔌 RPC backend disconnected: {backend_addr}",
                        'level': 'warning',
                        'details': {'backend': backend_addr}
                    }
                    logs.append(json.dumps(log_entry))

                    # Publish to Redis
                    if redis_publisher:
                        redis_publisher.publish_rpc_backend_disconnect(backend_addr)

                previous_state['rpc_backends'] = current_backends

            # Show status if coordinator is running
            if coordinator:
                process = getattr(coordinator, 'process', None)
                if process and process.poll() is None:  # Process is running
                    # Check if there's any recent activity by trying to read from stderr
                    # (llama-server logs to stderr)
                    # This is just a status check, not reading logs
                    current_time = time.time()
                    if current_time - previous_state['last_heartbeat'] >= 30:
                        backend_count = len(previous_state['rpc_backends'])
                        status_msg = {
                            'timestamp': time.time(),
                            'component': 'coordinator',
                            'type': 'status',
                            'message': f"✓ Coordinator active ({backend_count} RPC backends)",
                            'level': 'info',
                            'details': {
                                'backends': list(previous_state['rpc_backends']),
                                'model': coordinator_model
                            }
                        }
                        logs.append(json.dumps(status_msg))
                        previous_state['last_heartbeat'] = current_time

            # Send all log entries
            for log in logs:
                try:
                    ws.send(log)
                except Exception as e:
                    logger.error(f"Failed to send llama.cpp log: {e}")
                    raise

            # Heartbeat for distributed mode status
            if not enable_distributed:
                current_time = time.time()
                if current_time - previous_state['last_heartbeat'] >= 30:
                    heartbeat = {
                        'timestamp': time.time(),
                        'component': 'system',
                        'type': 'info',
                        'message': '📡 Distributed inference disabled',
                        'level': 'info'
                    }
                    ws.send(json.dumps(heartbeat))
                    previous_state['last_heartbeat'] = current_time

            # Check for state changes every 60 seconds (not aggressive polling)
            # This only detects coordinator start/stop, not active operation
            # For real-time logs, coordinator publishes to Redis pub/sub
            time.sleep(60)

        except Exception as e:
            logger.error(f"llama.cpp logs WebSocket error: {e}", exc_info=True)
            try:
                error_msg = {
                    'timestamp': time.time(),
                    'component': 'system',
                    'type': 'error',
                    'message': f'Error: {str(e)}',
                    'level': 'error'
                }
                ws.send(json.dumps(error_msg))
            except:
                pass
            break

def run_dashboard(host='0.0.0.0', port=8080, node_registry=None, sollol_lb=None, hybrid_router_ref=None, rpc_registry=None, redis_log_publisher=None):
    """Run the dashboard server."""
    global registry, load_balancer, hybrid_router, rpc_backend_registry, redis_publisher

    if node_registry is None:
        from node_registry import NodeRegistry
        registry = NodeRegistry()
        try:
            registry.add_node("http://localhost:11434", name="localhost", priority=10)
        except Exception as e:
            logger.warning(f"Could not add localhost node: {e}")
    else:
        registry = node_registry

    if sollol_lb is None:
        from sollol_load_balancer import SOLLOLLoadBalancer
        load_balancer = SOLLOLLoadBalancer(registry)
    else:
        load_balancer = sollol_lb

    # Set hybrid router for llama.cpp monitoring
    if hybrid_router_ref is not None:
        hybrid_router = hybrid_router_ref
        logger.info("🔧 llama.cpp monitoring enabled for dashboard")

    # Set RPC registry for RPC backend monitoring
    if rpc_registry is not None:
        rpc_backend_registry = rpc_registry
        logger.info(f"🔗 RPC backend monitoring enabled ({len(rpc_registry.backends)} backends)")

    # Set Redis publisher for log publishing
    if redis_log_publisher is not None:
        redis_publisher = redis_log_publisher
        logger.info(f"📡 Redis log publishing enabled (host: {redis_publisher.host}:{redis_publisher.port})")
    elif REDIS_AVAILABLE:
        # Try to use global publisher
        redis_publisher = get_global_publisher()
        if redis_publisher:
            logger.info("📡 Using global Redis log publisher")

    # Capture werkzeug logs and route them to the queue
    werkzeug_logger = logging.getLogger('werkzeug')
    for handler in werkzeug_logger.handlers[:]:
        werkzeug_logger.removeHandler(handler)
    werkzeug_logger.addHandler(QueueLogHandler(log_queue))

    logger.info(f"🚀 Starting SOLLOL Dashboard on http://{host}:{port}")
    
    # Use app.run for the development server, which supports flask-sock
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    run_dashboard()
