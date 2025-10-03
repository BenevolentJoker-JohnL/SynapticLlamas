# SOLLOL Dashboard

Real-time monitoring dashboard for SynapticLlamas' intelligent load balancing system.

## Overview

The SOLLOL Dashboard provides live visibility into:
- **System Health**: Overall status and node availability
- **Performance Metrics**: Latency, success rates, GPU utilization
- **Node Status**: Real-time health of all Ollama nodes
- **Active Alerts**: Warnings and errors from the system
- **Routing Intelligence**: Learned task patterns and routing decisions

## Quick Start

### 1. Install Dependencies

```bash
pip install flask flask-cors
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

### 2. Launch from Interactive Mode

```bash
python main.py --distributed
```

In the interactive prompt:

```
SynapticLlamas> dashboard
```

This launches the dashboard server on **http://localhost:8080**

### 3. Open in Browser

Navigate to: **http://localhost:8080**

The dashboard auto-refreshes every 3 seconds with live data.

## Standalone Mode

You can also run the dashboard server independently:

```bash
python dashboard_server.py
```

Then open http://localhost:8080 in your browser.

## API Endpoints

The dashboard server provides the following REST API endpoints:

### GET /api/dashboard

Returns complete dashboard data:

```json
{
  "status": {
    "healthy": true,
    "available_hosts": 3,
    "total_hosts": 3,
    "ray_workers": 0
  },
  "performance": {
    "avg_latency_ms": 250,
    "avg_success_rate": 0.98,
    "total_gpu_memory_mb": 32768
  },
  "hosts": [
    {
      "host": "http://localhost:11434",
      "status": "healthy",
      "latency_ms": 120,
      "success_rate": 0.99,
      "load": 0.45,
      "gpu_mb": 16384
    }
  ],
  "alerts": [],
  "routing": {
    "patterns_available": ["generation", "embedding", "classification"],
    "task_types_learned": 3
  }
}
```

### GET /api/stats

Returns detailed SOLLOL statistics:

```json
{
  "load_balancer": {
    "type": "SOLLOL",
    "version": "1.0.0",
    "intelligent_routing": true,
    "priority_queue": true,
    "adaptive_learning": true
  },
  "nodes": {
    "total": 3,
    "healthy": 3,
    "gpu": 2,
    "unhealthy": 0
  },
  "metrics": { ... },
  "performance_memory": { ... },
  "queue": { ... }
}
```

### GET /api/health

Health check endpoint:

```json
{
  "status": "ok",
  "service": "sollol-dashboard"
}
```

## Dashboard Features

### 🎯 Status Cards

Top-level KPIs showing:
- **System Status**: Overall health indicator
- **Active Hosts**: Available nodes vs total
- **Avg Latency**: Mean response time across all nodes
- **Success Rate**: Percentage of successful requests
- **GPU Memory**: Total GPU memory available
- **Ray Workers**: Distributed workers (if using Ray)

### 🖥️ Host Status Panel

Real-time view of all Ollama nodes:
- **URL**: Node endpoint
- **Status**: `healthy` / `degraded` / `offline`
- **Latency**: Current response time
- **Success Rate**: Request success percentage
- **Load**: Current utilization (0-100%)
- **GPU Memory**: Available GPU memory

Color coding:
- 🟢 **Green**: Healthy node
- 🟡 **Yellow**: Degraded (high latency or low success rate)
- 🔴 **Red**: Offline

### ⚠️ Active Alerts

Shows warnings and errors:
- **Node Offline**: When a node becomes unavailable
- **High Latency**: When latency exceeds 1000ms
- **Low Success Rate**: When success rate drops below 90%

### 🧠 Routing Intelligence

Displays learned routing patterns:
- **Task Types**: Categories of tasks the system has learned
- **Routing Patterns**: Common request patterns
- **Optimization**: Shows how routing improves over time

## Configuration

### Change Port

Edit `dashboard_server.py`:

```python
if __name__ == '__main__':
    run_dashboard(port=9090)  # Change from default 8080
```

Or modify the `run_dashboard()` call in `main.py`.

### Update Refresh Rate

Edit `dashboard.html`:

```javascript
// Change from 3000ms (3 seconds) to desired interval
refreshInterval = setInterval(fetchDashboard, 5000);  // 5 seconds
```

### Custom Styling

The dashboard uses a dark theme with purple/blue gradients. To customize:

1. Edit the `<style>` section in `dashboard.html`
2. Modify color variables:
   - Primary gradient: `#667eea` → `#764ba2`
   - Background: `#0a0e27`
   - Card background: `#1a1f3a`

## Troubleshooting

### Dashboard Not Loading

1. **Check server is running**:
   ```bash
   curl http://localhost:8080/api/health
   ```

2. **Check port availability**:
   ```bash
   lsof -i :8080
   ```

3. **Check Flask is installed**:
   ```bash
   pip show flask flask-cors
   ```

### No Data Showing

1. **Ensure nodes are registered**:
   ```
   SynapticLlamas> nodes
   ```

2. **Run a query first** to generate metrics:
   ```
   SynapticLlamas> explain quantum computing
   ```

3. **Check API response**:
   ```bash
   curl http://localhost:8080/api/dashboard
   ```

### CORS Errors

If accessing from a different host, ensure `flask-cors` is installed and CORS is enabled in `dashboard_server.py`:

```python
from flask_cors import CORS
app = Flask(__name__)
CORS(app)  # Enables CORS for all routes
```

## Architecture

```
┌─────────────────────────────────────────────┐
│          Browser (localhost:8080)           │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │         dashboard.html                  │ │
│  │  - Auto-refresh every 3s                │ │
│  │  - Fetches /api/dashboard               │ │
│  │  - Updates UI with live data            │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                      ↓ HTTP GET
┌─────────────────────────────────────────────┐
│      Flask Server (dashboard_server.py)     │
│                                              │
│  ┌────────────────────────────────────────┐ │
│  │  /api/dashboard                         │ │
│  │  - Calls load_balancer.get_stats()     │ │
│  │  - Aggregates node metrics              │ │
│  │  - Formats response JSON                │ │
│  └────────────────────────────────────────┘ │
└─────────────────────────────────────────────┘
                      ↓
┌─────────────────────────────────────────────┐
│         SOLLOLLoadBalancer                  │
│                                              │
│  - NodeRegistry (node health/metrics)       │
│  - MetricsCollector (routing stats)         │
│  - PerformanceMemory (adaptive learning)    │
│  - PriorityQueue (task scheduling)          │
└─────────────────────────────────────────────┘
```

## Integration with SynapticLlamas

The dashboard automatically connects to the active load balancer used by SynapticLlamas:

1. **Distributed Mode**: Uses SOLLOLLoadBalancer with intelligent routing
2. **Standard Mode**: Shows single-node metrics
3. **Dask Mode**: Displays Dask cluster info

The dashboard provides **real-time visibility** into SOLLOL's routing decisions, helping you:
- Monitor system health
- Debug routing issues
- Optimize node configuration
- Track performance improvements
- Understand adaptive learning

## Next Steps

1. **Add Nodes**: Use `add <url>` or `discover` to add more Ollama nodes
2. **Run Queries**: Execute queries to populate metrics and routing data
3. **Monitor Performance**: Watch the dashboard to see SOLLOL's intelligent routing in action
4. **Optimize**: Adjust node priorities and configuration based on dashboard insights

For more information, see:
- `SOLLOL_INTEGRATED.md` - SOLLOL integration details
- `README.md` - SynapticLlamas overview
- `ARCHITECTURE.md` - System architecture
