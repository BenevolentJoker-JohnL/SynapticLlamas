# SynapticLlamas + SOLLOL Integration

> **Note:** As of v0.9.7, SynapticLlamas uses SOLLOL as a package dependency instead of an embedded copy. This eliminates code duplication and ensures bug fixes benefit both projects. See [SOLLOL on GitHub](https://github.com/BenevolentJoker-JohnL/SOLLOL).

## Overview

SynapticLlamas now uses **SOLLOL (Super Ollama Load Balancer)** as its intelligent routing backend. This provides:

- ✅ **Intelligent routing** based on request complexity
- ✅ **Automatic failover** when nodes are down
- ✅ **Priority-based scheduling** for different agent types
- ✅ **Real-time performance tracking**
- ✅ **Transparent operation** - works exactly like direct Ollama

## Quick Start

### 1. Start SOLLOL Server

```bash
# Start SOLLOL with your Ollama nodes
sollol serve --host 0.0.0.0 --port 8000

# SOLLOL will automatically discover Ollama nodes on:
# - http://localhost:11434
# - http://localhost:11435
# - http://localhost:11436
# etc.

# Or manually configure hosts
sollol serve --host 0.0.0.0 --port 8000 \
  --ollama-hosts http://10.0.0.2:11434,http://10.0.0.3:11434
```

### 2. Run SynapticLlamas

SynapticLlamas will **automatically use SOLLOL** if it's running:

```bash
# Standard mode (auto-detects SOLLOL)
python main.py

# Interactive mode
python main.py -i "Explain quantum computing"
```

### 3. Verify SOLLOL Integration

```python
from sollol_adapter import get_adapter

adapter = get_adapter()
print(f"Using: {adapter.get_ollama_url()}")
print(f"SOLLOL available: {adapter.check_sollol_available()}")
```

## Architecture

```
┌─────────────────────────────────────────────┐
│         SynapticLlamas Agents               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │Researcher│  │  Critic  │  │  Editor  │  │
│  │Priority 7│  │Priority 6│  │Priority 5│  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└───────┼─────────────┼─────────────┼─────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
                      ▼
        ┌─────────────────────────────────────┐
        │      SOLLOL Gateway :8000           │
        │  🧠 Intelligent Routing Engine      │
        │  🎯 Priority Queue System           │
        │  📊 Performance Tracking            │
        └──────┬──────────┬──────────┬────────┘
               │          │          │
               ▼          ▼          ▼
         ┌─────────┐┌─────────┐┌─────────┐
         │ Ollama  ││ Ollama  ││ Ollama  │
         │ :11434  ││ :11435  ││ :11436  │
         │  (GPU)  ││  (GPU)  ││  (CPU)  │
         └─────────┘└─────────┘└─────────┘
```

## Agent Priorities

SOLLOL routes agents with different priorities:

| Agent        | Priority | Routing Strategy                    |
|--------------|----------|-------------------------------------|
| Researcher   | 7 (High) | Fast GPU nodes, low latency         |
| Critic       | 6        | GPU nodes with good success rate    |
| Editor       | 5        | Balanced routing                    |
| Summarizer   | 4        | Standard nodes                      |
| Background   | 2 (Low)  | Available capacity, can queue       |

## Configuration

### Environment Variables

```bash
# Enable/disable SOLLOL
export USE_SOLLOL=true

# SOLLOL server location
export SOLLOL_HOST=localhost
export SOLLOL_PORT=8000

# Run SynapticLlamas
python main.py
```

### Programmatic Configuration

```python
from sollol_adapter import configure_sollol

# Configure SOLLOL
configure_sollol(
    host="10.0.0.10",
    port=8000,
    enabled=True
)

# Create agents (will automatically use SOLLOL)
from agents.researcher import Researcher
agent = Researcher()  # Automatically uses SOLLOL
```

### Disable SOLLOL (Direct Ollama)

```python
from sollol_adapter import configure_sollol

# Disable SOLLOL, use direct Ollama
configure_sollol(enabled=False)

# Or via environment
export USE_SOLLOL=false
python main.py
```

## Benefits Over Direct Ollama

### Before (Direct Ollama)

```python
# Agents connect directly to single Ollama instance
agent = Researcher(ollama_url="http://localhost:11434")

# Problems:
# ❌ Single point of failure
# ❌ No load balancing
# ❌ Manual failover required
# ❌ All agents treated equally
```

### After (SOLLOL)

```python
# Agents automatically use SOLLOL
agent = Researcher()  # Intelligent routing enabled

# Benefits:
# ✅ Automatic failover to healthy nodes
# ✅ Priority-based routing (high priority = fast nodes)
# ✅ Load balancing across multiple nodes
# ✅ 30-40% faster responses
# ✅ Real-time performance tracking
```

## Monitoring

### Check Routing Decisions

SOLLOL adds routing metadata to all responses:

```python
response = agent.process("Analyze this data")

# Check routing information
routing = response.get('_sollol_routing', {})
print(f"Routed to: {routing.get('host')}")
print(f"Task type: {routing.get('task_type')}")
print(f"Decision score: {routing.get('decision_score')}")
print(f"Reasoning: {routing.get('reasoning')}")
```

### SOLLOL Dashboard

```bash
# Open dashboard
open http://localhost:8000/dashboard.html

# Shows:
# - Live routing decisions
# - Node performance metrics
# - Queue statistics
# - Alert detection
```

### Prometheus Metrics

```bash
# Metrics endpoint
curl http://localhost:8000/metrics

# Metrics include:
# - Request rates per agent
# - Latency percentiles
# - Success rates
# - Node health
```

## Examples

### Basic Usage

```python
from agents.researcher import Researcher
from agents.critic import Critic
from agents.editor import Editor

# Create agents (automatically use SOLLOL)
researcher = Researcher()  # Priority 7
critic = Critic()          # Priority 6
editor = Editor()          # Priority 5

# SOLLOL routes each based on priority:
# - Researcher gets fastest GPU nodes
# - Critic gets fast nodes with good success rate
# - Editor gets balanced routing

research = researcher.process("Research quantum computing")
analysis = critic.process("Analyze the research")
summary = editor.process("Summarize findings")
```

### Distributed Mode

```python
from main import main

# SynapticLlamas with SOLLOL
# SOLLOL handles all load balancing automatically
python main.py --distributed

# No need for --add-node or --discover
# SOLLOL manages all Ollama nodes
```

### Parallel Execution

```python
import concurrent.futures
from agents.researcher import Researcher

# Multiple agents running concurrently
# SOLLOL intelligently distributes across nodes
agents = [Researcher() for _ in range(10)]

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [
        executor.submit(agent.process, f"Query {i}")
        for i, agent in enumerate(agents)
    ]

    results = [f.result() for f in futures]

# SOLLOL:
# - Routes to optimal nodes
# - Balances load automatically
# - Handles failures gracefully
```

## Troubleshooting

### SOLLOL Not Available

```python
from sollol_adapter import get_adapter

adapter = get_adapter()

if not adapter.check_sollol_available():
    print("❌ SOLLOL not running")
    print("Start with: sollol serve --host 0.0.0.0 --port 8000")
else:
    print("✅ SOLLOL is running")
```

### Fallback to Direct Ollama

If SOLLOL is not available, SynapticLlamas can fallback:

```python
# Automatic fallback
export USE_SOLLOL=false
python main.py

# Or specify Ollama URL directly
from agents.researcher import Researcher
agent = Researcher(ollama_url="http://localhost:11434")
```

### Check Agent Priorities

```python
from sollol_adapter import get_adapter

adapter = get_adapter()

print(f"Researcher priority: {adapter.get_priority_for_agent('Researcher')}")
print(f"Critic priority: {adapter.get_priority_for_agent('Critic')}")
print(f"Editor priority: {adapter.get_priority_for_agent('Editor')}")
```

## Performance

### Expected Improvements with SOLLOL

| Metric               | Direct Ollama | With SOLLOL | Improvement |
|----------------------|---------------|-------------|-------------|
| Avg Latency          | ~15s          | ~9s         | **-40%**    |
| P95 Latency          | ~35s          | ~18s        | **-49%**    |
| Success Rate         | 94%           | 98%         | **+4pp**    |
| GPU Utilization      | 45%           | 78%         | **+73%**    |
| Throughput (req/s)   | 8.5           | 13.2        | **+55%**    |

### Benchmark

```bash
# Run benchmark
python benchmark.py --sollol

# Results show:
# - Routing overhead: <10ms
# - Overall latency improvement: 30-40%
# - Automatic failover: <2s recovery
```

## Best Practices

1. **Always start SOLLOL first**
   ```bash
   sollol serve --host 0.0.0.0 --port 8000
   ```

2. **Let agents use default priorities**
   ```python
   agent = Researcher()  # Uses priority 7 automatically
   ```

3. **Monitor dashboard for bottlenecks**
   ```bash
   open http://localhost:8000/dashboard.html
   ```

4. **Use environment variables for deployment**
   ```bash
   export SOLLOL_HOST=sollol-prod.company.com
   export SOLLOL_PORT=8000
   ```

5. **Check routing decisions**
   ```python
   response = agent.process(query)
   print(response.get('_sollol_routing'))
   ```

## Migration Guide

### From Direct Ollama

**Before:**
```python
from agents.researcher import Researcher

# Hardcoded Ollama URL
agent = Researcher(ollama_url="http://localhost:11434")
```

**After:**
```python
from agents.researcher import Researcher

# Automatic SOLLOL detection
agent = Researcher()  # That's it!
```

### From Custom Load Balancer

**Before:**
```python
from load_balancer import OllamaLoadBalancer
from node_registry import NodeRegistry

registry = NodeRegistry()
registry.add_node("http://node1:11434")
registry.add_node("http://node2:11434")
balancer = OllamaLoadBalancer(registry)

# Manual routing
node = balancer.get_node()
agent = Researcher(ollama_url=node.url)
```

**After:**
```python
from agents.researcher import Researcher

# SOLLOL handles everything
agent = Researcher()
```

## Learn More

- [SOLLOL Documentation](../README.md)
- [Architecture Details](../ARCHITECTURE.md)
- [Benchmarks](../BENCHMARKS.md)
- [SynapticLlamas Docs](./README.md)
