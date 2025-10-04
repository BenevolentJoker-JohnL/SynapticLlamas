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

    return {
        'status': {'healthy': bool(healthy_nodes), 'available_hosts': len(healthy_nodes), 'total_hosts': len(all_nodes), 'ray_workers': 0},
        'performance': {'avg_latency_ms': avg_latency, 'avg_success_rate': avg_success_rate, 'total_gpu_memory_mb': total_gpu_memory},
        'hosts': hosts,
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
        time.sleep(10)  # Update every 10 seconds

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
    """WebSocket endpoint for streaming Ollama node activity."""
    logger.info("Ollama logs WebSocket client connected.")

    # Send initial connection message
    try:
        init_msg = {
            'timestamp': time.time(),
            'node': 'system',
            'type': 'info',
            'message': '🔌 Connected to Ollama monitoring',
            'level': 'info'
        }
        ws.send(json.dumps(init_msg))
    except Exception as e:
        logger.error(f"Failed to send init message: {e}")

    # Track previous state to detect changes
    previous_state = {}

    while True:
        try:
            if not registry:
                logger.warning("No registry available for Ollama logs")
                time.sleep(2)
                continue

            if len(registry.nodes) == 0:
                logger.warning("Registry has no nodes")
                time.sleep(2)
                continue

            # Poll all nodes for their current state
            logs = []
            for url, node in registry.nodes.items():
                try:
                    # Get currently loaded models
                    response = requests.get(f"{url}/api/ps", timeout=2)
                    if response.status_code == 200:
                        data = response.json()
                        models = data.get('models', [])

                        # Create state snapshot
                        current_state = {
                            'loaded_models': [m['name'] for m in models],
                            'total_vram': sum(m.get('size_vram', 0) for m in models),
                            'model_count': len(models),
                        }

                        # Detect changes
                        prev = previous_state.get(url, {})

                        # New models loaded
                        prev_models = set(prev.get('loaded_models', []))
                        curr_models = set(current_state['loaded_models'])

                        newly_loaded = curr_models - prev_models
                        unloaded = prev_models - curr_models

                        if newly_loaded:
                            for model in newly_loaded:
                                log_entry = {
                                    'timestamp': time.time(),
                                    'node': url,
                                    'type': 'model_load',
                                    'message': f"✅ Model loaded: {model}",
                                    'level': 'info'
                                }
                                logs.append(json.dumps(log_entry))

                        if unloaded:
                            for model in unloaded:
                                log_entry = {
                                    'timestamp': time.time(),
                                    'node': url,
                                    'type': 'model_unload',
                                    'message': f"⏹️  Model unloaded: {model}",
                                    'level': 'info'
                                }
                                logs.append(json.dumps(log_entry))

                        # Only log when models are actively processing (check processing time)
                        if models:
                            for model_info in models:
                                model_name = model_info['name']
                                # Check if model is actively processing by looking at processing time
                                processor = model_info.get('processor', {})
                                if processor:  # Model is actively being used
                                    size_vram = model_info.get('size_vram', 0) / (1024**3)
                                    log_entry = {
                                        'timestamp': time.time(),
                                        'node': url,
                                        'type': 'model_processing',
                                        'message': f"🔄 Processing: {model_name} (VRAM: {size_vram:.2f}GB)",
                                        'level': 'info'
                                    }
                                    logs.append(json.dumps(log_entry))

                        # Store current state
                        previous_state[url] = current_state
                        previous_state[url]['was_reachable'] = True

                except Exception as e:
                    # Node unreachable
                    if url in previous_state and previous_state[url].get('was_reachable', True):
                        log_entry = {
                            'timestamp': time.time(),
                            'node': url,
                            'type': 'error',
                            'message': f"Node unreachable: {str(e)}",
                            'level': 'error'
                        }
                        logs.append(json.dumps(log_entry))
                        previous_state[url] = {'was_reachable': False}

            # Send all log entries
            for log in logs:
                try:
                    ws.send(log)
                except Exception as e:
                    logger.error(f"Failed to send Ollama log: {e}")
                    raise

            # Only send heartbeat every 30 seconds if idle (no logs)
            if len(logs) == 0:
                # Track last heartbeat time
                if not hasattr(ws, '_last_heartbeat'):
                    ws._last_heartbeat = 0

                current_time = time.time()
                if current_time - ws._last_heartbeat >= 30:  # 30 seconds
                    heartbeat = {
                        'timestamp': time.time(),
                        'node': 'system',
                        'type': 'debug',
                        'message': f'✓ Monitoring {len(registry.nodes)} nodes (idle)',
                        'level': 'info'
                    }
                    ws.send(json.dumps(heartbeat))
                    ws._last_heartbeat = current_time

            # Poll every 2 seconds
            time.sleep(2)

        except Exception as e:
            logger.error(f"Ollama logs WebSocket error: {e}", exc_info=True)
            # Send error to client
            try:
                error_msg = {
                    'timestamp': time.time(),
                    'node': 'system',
                    'type': 'error',
                    'message': f'Error: {str(e)}',
                    'level': 'error'
                }
                ws.send(json.dumps(error_msg))
            except:
                pass
            break

def run_dashboard(host='0.0.0.0', port=8080, node_registry=None, sollol_lb=None):
    """Run the dashboard server."""
    global registry, load_balancer

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
