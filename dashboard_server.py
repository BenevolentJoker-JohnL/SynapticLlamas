"""
SOLLOL Dashboard Server for SynapticLlamas

Serves the SOLLOL monitoring dashboard and provides API endpoints
for real-time load balancer statistics.
"""
from flask import Flask, jsonify, send_file
from flask_cors import CORS
import logging
from datetime import datetime
from node_registry import NodeRegistry
from sollol_load_balancer import SOLLOLLoadBalancer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for dashboard

# Initialize registry and load balancer
registry = NodeRegistry()
load_balancer = SOLLOLLoadBalancer(registry)

# Add localhost node if none exist
if len(registry) == 0:
    try:
        registry.add_node("http://localhost:11434", name="localhost", priority=10)
    except Exception as e:
        logger.warning(f"Could not add localhost node: {e}")


@app.route('/')
def index():
    """Serve the dashboard HTML."""
    return send_file('dashboard.html')


@app.route('/api/dashboard')
def dashboard_data():
    """
    Get comprehensive dashboard data.

    Returns JSON with system status, performance metrics, hosts, alerts, and routing info.
    """
    stats = load_balancer.get_stats()
    healthy_nodes = registry.get_healthy_nodes()
    all_nodes = registry.nodes

    # Calculate aggregated metrics
    total_requests = sum(node.metrics.total_requests for node in all_nodes)
    successful_requests = sum(node.metrics.successful_requests for node in all_nodes)
    avg_success_rate = successful_requests / total_requests if total_requests > 0 else 1.0

    avg_latency = sum(node.metrics.avg_latency for node in healthy_nodes) / len(healthy_nodes) if healthy_nodes else 0
    total_gpu_memory = sum(
        node.capabilities.gpu_memory_mb
        for node in all_nodes
        if node.capabilities and node.capabilities.has_gpu
    )

    # Build host data
    hosts = []
    for node in all_nodes:
        host_data = {
            'host': node.url,
            'status': 'healthy' if node.is_healthy else 'offline',
            'latency_ms': node.metrics.avg_latency,
            'success_rate': (
                node.metrics.successful_requests / node.metrics.total_requests
                if node.metrics.total_requests > 0 else 1.0
            ),
            'load': node.calculate_load_score() / 100.0,  # Normalize to 0-1
            'gpu_mb': node.capabilities.gpu_memory_mb if node.capabilities else 0
        }

        # Mark degraded nodes (high latency or low success rate)
        if node.is_healthy and (node.metrics.avg_latency > 1000 or host_data['success_rate'] < 0.9):
            host_data['status'] = 'degraded'

        hosts.append(host_data)

    # Build alerts
    alerts = []
    for node in all_nodes:
        if not node.is_healthy:
            alerts.append({
                'severity': 'error',
                'message': f'Node {node.url} is offline',
                'timestamp': node.last_health_check.isoformat() if node.last_health_check else datetime.now().isoformat()
            })
        elif node.metrics.avg_latency > 1000:
            alerts.append({
                'severity': 'warning',
                'message': f'High latency on {node.url}: {node.metrics.avg_latency:.0f}ms',
                'timestamp': datetime.now().isoformat()
            })

    # Get routing patterns from metrics
    routing_patterns = []
    task_types_learned = 0
    if hasattr(load_balancer.metrics, 'get_summary'):
        metrics_summary = load_balancer.metrics.get_summary()
        if 'task_types' in metrics_summary:
            routing_patterns = list(metrics_summary['task_types'].keys())
            task_types_learned = len(routing_patterns)

    return jsonify({
        'status': {
            'healthy': len(healthy_nodes) > 0,
            'available_hosts': len(healthy_nodes),
            'total_hosts': len(all_nodes),
            'ray_workers': 0  # Not using Ray in embedded mode
        },
        'performance': {
            'avg_latency_ms': avg_latency,
            'avg_success_rate': avg_success_rate,
            'total_gpu_memory_mb': total_gpu_memory
        },
        'hosts': hosts,
        'alerts': alerts,
        'routing': {
            'patterns_available': routing_patterns,
            'task_types_learned': task_types_learned
        }
    })


@app.route('/api/stats')
def detailed_stats():
    """Get detailed SOLLOL statistics."""
    return jsonify(load_balancer.get_stats())


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'service': 'sollol-dashboard'})


def run_dashboard(host='0.0.0.0', port=8080, production=True):
    """
    Run the dashboard server.

    Args:
        host: Host to bind to (default: 0.0.0.0)
        port: Port to bind to (default: 8080)
        production: Use production WSGI server (default: True)
    """
    logger.info(f"🚀 Starting SOLLOL Dashboard on http://{host}:{port}")
    logger.info(f"   Dashboard: http://{host}:{port}/")
    logger.info(f"   API Stats: http://{host}:{port}/api/dashboard")

    if production:
        try:
            # Use waitress for production (pure Python, cross-platform)
            from waitress import serve
            logger.info("   Using Waitress production server")
            serve(app, host=host, port=port, threads=4, _quiet=True)
        except ImportError:
            logger.warning("   Waitress not installed, falling back to Flask dev server")
            logger.warning("   Install waitress for production: pip install waitress")
            app.run(host=host, port=port, debug=False, use_reloader=False)
    else:
        app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    run_dashboard()
