# 🧠 SynapticLlamas

**Distributed Parallel Agent Playground** - A portfolio-ready distributed AI orchestration system with intelligent load balancing, adaptive routing, and robust JSON standardization.

## Overview

SynapticLlamas demonstrates **distributed AI agent orchestration** by running multiple specialized agents in parallel across an Ollama cluster. Each agent processes input from different perspectives, with intelligent load balancing, GPU routing, and automatic strategy adaptation.

## Key Features

- ✅ **Distributed Load Balancing** - Intelligent routing across multiple Ollama nodes
- ✅ **Network Discovery** - Auto-discover Ollama instances on your network
- ✅ **Adaptive Strategy Selection** - Automatically chooses optimal execution mode (single/parallel/GPU)
- ✅ **GPU Routing** - Prioritize GPU-enabled nodes for faster inference
- ✅ **Active GPU Controller** 🆕 - Ensures models actually run on GPU (not just route to GPU nodes)
- ✅ **Layer Partitioning** 🆕 - Split 70B+ models across multiple nodes for distributed inference
- ✅ **FlockParser RAG Integration** 🆕 - Enhance research reports with PDF document context
- ✅ **Health Monitoring** - Continuous health checks and node failure handling
- ✅ **JSON Pipeline** - Robust extraction and standardization (handles non-compliant models)
- ✅ **Interactive CLI** - REPL-style interface with node management commands
- ✅ **Performance Benchmarking** - Auto-benchmark to find fastest strategy
- ✅ **Modular Architecture** - Easy to extend with new agents and strategies

## Architecture

```
SynapticLlamas/
├─ agents/
│  ├─ base_agent.py              # Abstract base with Ollama + JSON pipeline
│  ├─ researcher.py              # Extracts key facts and context
│  ├─ critic.py                  # Analyzes issues, biases, recommendations
│  └─ editor.py                  # Summarizes and polishes output
├─ ollama_node.py                # Node abstraction with health/metrics
├─ node_registry.py              # Node management + discovery
├─ load_balancer.py              # Intelligent routing strategies
├─ adaptive_strategy.py          # Auto-selects execution mode
├─ distributed_orchestrator.py   # Distributed execution coordinator
├─ json_pipeline.py              # Robust JSON extraction
├─ orchestrator.py               # Standard parallel executor
├─ aggregator.py                 # Output merging logic
├─ main.py                       # Interactive CLI
└─ requirements.txt
```

## Installation

```bash
cd SynapticLlamas
pip install -r requirements.txt
```

**Prerequisites:**
- Python 3.8+
- Ollama running locally (`http://localhost:11434`)

## Usage

### Standard Mode (Single Node)

```bash
# Interactive mode
python main.py

# Single query
python main.py -i "Explain quantum computing"
```

### Distributed Mode (Multi-Node Load Balancing)

```bash
# Start with distributed mode
python main.py --distributed

# Auto-discover nodes on network
python main.py --distributed --discover 192.168.1.0/24

# Add specific node
python main.py --distributed --add-node http://192.168.1.100:11434

# Load saved configuration
python main.py --distributed --load-config nodes.json
```

### Dask Mode (True Distributed Cluster)

```bash
# Local Dask cluster (automatic)
python main.py --dask

# Connect to existing Dask scheduler
python main.py --dask --dask-scheduler tcp://192.168.1.50:8786

# With Ollama node discovery
python main.py --dask --discover 192.168.1.0/24
```

**Dask Setup (on separate machines):**

```bash
# On scheduler machine
dask scheduler

# On worker machines
dask worker tcp://192.168.1.50:8786
```

The Dask executor will:
- Distribute agents across Dask workers (different machines)
- Use Ollama load balancer to route inference to available Ollama nodes
- Show live dashboard for monitoring

### Interactive Commands (Distributed/Dask Mode)

```
SynapticLlamas> nodes              # List all Ollama nodes
SynapticLlamas> add http://...     # Add an Ollama node
SynapticLlamas> remove http://...  # Remove an Ollama node
SynapticLlamas> discover 192.168.1.0/24  # Discover Ollama nodes
SynapticLlamas> health             # Health check all Ollama nodes
SynapticLlamas> save nodes.json    # Save node config
SynapticLlamas> load nodes.json    # Load node config
SynapticLlamas> rag on/off         # Toggle FlockParser RAG enhancement
SynapticLlamas> dask               # Show Dask cluster info (Dask mode only)
SynapticLlamas> metrics            # Show performance metrics
```

## FlockParser RAG Integration

SynapticLlamas integrates with [FlockParser](https://github.com/your-username/FlockParser) to enhance research reports with relevant PDF document context through Retrieval-Augmented Generation (RAG).

### How It Works

When RAG is enabled and you ask a research question, SynapticLlamas will:
1. Query FlockParser's document knowledge base for relevant content
2. Inject the top 15 most relevant PDF excerpts into the research prompt (up to 2000 tokens)
3. Generate research reports that cite and incorporate information from your PDFs
4. Display which source documents were used in the output

### Setup

1. **Install FlockParser** at `/home/joker/FlockParser` (or configure path in `flockparser_adapter.py`)
2. **Index your PDFs** using FlockParser's CLI
3. **Enable RAG** in SynapticLlamas:
   ```bash
   SynapticLlamas> rag on
   ```

### Usage

```bash
# Enable RAG enhancement
SynapticLlamas> rag on

# Ask a research question
SynapticLlamas> Explain quantum entanglement

# Output will show:
# 📖 RAG Enhancement: Using 3 source document(s)
#    • quantum_physics_intro.pdf
#    • entanglement_experiments.pdf
#    • bell_theorem.pdf
```

The generated research report will incorporate information from these PDFs with proper citations.

### Requirements

- FlockParser installed at `/home/joker/FlockParser`
- PDFs indexed in FlockParser's knowledge base
- Ollama with `mxbai-embed-large` model for embeddings

## How It Handles Non-Compliant Models

The **JSON Pipeline** automatically:

1. **Tries `format: json` first** - Requests JSON output from Ollama
2. **Falls back gracefully** - If model doesn't support it, retries without format parameter
3. **Extracts JSON from markdown** - Handles ```json blocks, code fences, plain text
4. **Fixes malformed JSON** - Corrects trailing commas, unquoted keys, single quotes
5. **Wraps as fallback** - If all else fails, wraps raw text in standardized JSON structure

## JSON Output Structure

All agent outputs follow this standard:

```json
{
  "pipeline": "SynapticLlamas",
  "agent_count": 3,
  "agents": ["Researcher", "Critic", "Editor"],
  "outputs": [
    {
      "agent": "Researcher",
      "status": "success",
      "format": "json",
      "data": { ... }
    }
  ]
}
```

## Extending

### Add a New Agent

```python
# agents/summarizer.py
from .base_agent import BaseAgent

class Summarizer(BaseAgent):
    def __init__(self, model="llama3.2"):
        super().__init__("Summarizer", model)

    def process(self, input_data):
        system_prompt = "You are a summarization agent..."
        prompt = f"Summarize: {input_data}"
        return self.call_ollama(prompt, system_prompt)
```

Register in `orchestrator.py`:

```python
from agents.summarizer import Summarizer

agents = [
    Researcher(model),
    Critic(model),
    Editor(model),
    Summarizer(model)  # Add here
]
```

## Performance

Typical execution (3 agents, llama3.2):
- **Parallel**: ~8-15 seconds
- **Sequential**: ~25-40 seconds

## Adaptive Strategy Selection

The system automatically chooses the **fastest execution strategy**:

| Strategy | When Used | Description |
|----------|-----------|-------------|
| **SINGLE_NODE** | 1-2 agents, 1 node | Sequential execution on single node |
| **PARALLEL_SAME_NODE** | 3+ agents, 1 node | Parallel on same node |
| **PARALLEL_MULTI_NODE** | Multiple nodes available | Distribute agents across nodes |
| **GPU_ROUTING** | GPU nodes available | Route to GPU-enabled nodes first |

The selector learns from benchmark history and adapts over time.

## Load Balancing Strategies

- **LEAST_LOADED** - Route to node with lowest current load (default)
- **ROUND_ROBIN** - Rotate through nodes evenly
- **PRIORITY** - Use highest priority nodes first
- **GPU_FIRST** - Prefer GPU nodes, fallback to CPU
- **RANDOM** - Random selection

## Node Discovery

```python
# Discover Ollama nodes on local network
python main.py --distributed --discover 192.168.1.0/24

# The system:
# 1. Scans IP range in parallel (50 workers)
# 2. Checks for open port 11434
# 3. Verifies Ollama API is running
# 4. Probes for GPU capabilities
# 5. Auto-registers healthy nodes
```

## Active GPU Controller 🆕

SOLLOL now includes **active GPU controller integration** - ensuring that when the intelligent router routes to GPU nodes, models actually load on GPU (not CPU). Without this, SOLLOL's performance promise would be broken.

### The Problem

**Without active GPU control:**
```
SOLLOL routes to GPU node ✅
Model loads on CPU anyway ❌
Takes 45 seconds instead of 2 ❌  (20x slower!)
```

**With active GPU control:**
```
SOLLOL routes to GPU node ✅
GPU controller forces model onto GPU ✅
Takes 2 seconds as expected ✅
```

### Features

- **Automatic GPU verification**: After routing to GPU node, verifies model is on GPU
- **Force GPU load**: If model is on CPU, automatically forces it onto GPU
- **Pre-warming**: Pre-load critical models on GPU nodes to avoid first-request delays
- **Cluster optimization**: Intelligently place models across GPU/CPU nodes
- **Performance validation**: Closed-loop feedback ensures routing decisions match reality

### Usage

```python
from sollol_load_balancer import SOLLOLLoadBalancer
from node_registry import NodeRegistry

# GPU controller is enabled by default
registry = NodeRegistry()
registry.add_node("http://10.9.66.124:11434")  # GPU node

load_balancer = SOLLOLLoadBalancer(registry, enable_gpu_control=True)

# Pre-warm critical models on GPU nodes
load_balancer.pre_warm_gpu_models([
    "mxbai-embed-large",
    "llama3.1"
])

# Show GPU/CPU status
load_balancer.print_gpu_status()

# Now when routing, models are guaranteed to be on GPU
decision = load_balancer.route_request({
    'model': 'mxbai-embed-large',
    'prompt': 'embedding request'
})
# ✅ Routed to GPU node AND model is on GPU
```

### Performance Impact

**Embedding (mxbai-embed-large, 1000 documents):**
- GPU: ~2 seconds ⚡
- CPU: ~45 seconds 🐌
- **Speedup: 20x faster with GPU controller**

**Generation (llama3.1, 500 tokens):**
- GPU: ~3 seconds ⚡
- CPU: ~60 seconds 🐌
- **Speedup: 20x faster with GPU controller**

## Layer Partitioning for Large Models 🆕

SynapticLlamas now supports **layer partitioning** - the ability to split large models (70B+) across multiple nodes for distributed inference. This enables running models that don't fit on a single GPU.

### Quick Example

```python
from node_registry import NodeRegistry

# Setup registry
registry = NodeRegistry()
registry.add_node("http://192.168.1.10:11434", "gpu-node-1")
registry.add_node("http://192.168.1.11:11434", "gpu-node-2")

# Create cluster for Llama-70B
cluster = registry.create_cluster(
    name="llama70b-cluster",
    node_urls=[
        "http://192.168.1.10:11434",
        "http://192.168.1.11:11434"
    ],
    model="llama2:70b",
    partitioning_strategy="even"  # Split layers evenly
)

# Smart routing: small models → individual nodes, large models → clusters
worker = registry.get_worker_for_model("llama2:70b")  # Returns cluster
worker = registry.get_worker_for_model("llama3.2")    # Returns single node
```

### How It Works

**Architecture:**
```
Small Model (llama3.2):
GPU Node 1: [Full model] → Fast inference
GPU Node 2: [Full model] → Load balanced

Large Model (llama2:70b):
GPU Node 1: [Layers 0-39]  ┐
GPU Node 2: [Layers 40-79] ┴→ Distributed inference
```

**Features:**
- Automatic layer distribution (even or memory-aware)
- Cluster health checking (all nodes must be healthy)
- Smart routing (large models → clusters, small models → individual nodes)
- Support for multiple models: llama2:70b, llama3:70b, mixtral:8x7b

See [node_cluster.py](node_cluster.py) for implementation details.

## Performance

**Example setup: 3 nodes, llama3.2**

| Mode | Execution Time | Throughput |
|------|----------------|------------|
| Sequential (single) | ~35s | 0.09 agents/s |
| Parallel (single) | ~12s | 0.25 agents/s |
| Distributed (3 nodes) | ~5s | 0.60 agents/s |
| GPU routing | ~3s | 1.00 agents/s |
| **Cluster (70B model)** | ~15s | **0.2 agents/s** ✨ |

## Architecture Modes

### Standard Mode
- Single machine, ThreadPoolExecutor
- Agents run in parallel on one Ollama instance

### Distributed Mode
- Multi-node Ollama load balancing
- Adaptive strategy selection (single/parallel/GPU)
- Health monitoring and failover
- No separate cluster needed

### Dask Mode
- True distributed computing across machines
- Dask scheduler + workers on separate nodes
- Ollama load balancer routes inference
- Best for: Multi-machine setups, heavy workloads

**When to use which:**
- **Standard**: Single machine, quick setup
- **Distributed**: Multiple Ollama nodes, adaptive routing
- **Dask**: Multi-machine cluster, maximum parallelism

## Limitations & Trade-offs

Understanding the constraints and design decisions:

### Current Limitations

**Performance:**
- ⚠️ **Inference Speed** - Limited by Ollama backend performance; CPU-only nodes can take 5+ minutes per agent
- ⚠️ **Network Latency** - Multi-node execution adds network overhead; may not improve speed with slow connections
- ⚠️ **Sequential Bottlenecks** - Collaborative workflow is inherently sequential (Researcher → Critic → Editor)
- ⚠️ **Memory Usage** - Each agent loads model into memory; 3+ agents can require significant RAM

**Scalability:**
- ⚠️ **Node Discovery** - Network scanning can be slow on large subnets (100+ IPs); timeout-dependent
- ⚠️ **Concurrent Queries** - No built-in queuing; multiple simultaneous queries may overwhelm nodes
- ⚠️ **State Management** - No persistence; node registry and metrics lost on restart

**Quality:**
- ⚠️ **Model Dependence** - Output quality depends entirely on underlying Ollama models
- ⚠️ **JSON Reliability** - Some models struggle with JSON; fallback wrapping may lose structure
- ⚠️ **AST Voting** - Quality voting adds 3+ additional inference calls; expensive on CPU-only hardware
- ⚠️ **Context Limits** - Long documents may exceed model context windows; no automatic chunking

**Robustness:**
- ⚠️ **Node Failures** - Limited retry logic; transient network issues can fail queries
- ⚠️ **Error Recovery** - Partial failures (1 of 3 agents fails) return incomplete results
- ⚠️ **Timeout Handling** - Fixed timeouts; very slow hardware may need manual configuration

**Security:**
- ⚠️ **No Authentication** - Ollama nodes assumed to be on trusted networks
- ⚠️ **Input Validation** - Limited sanitization of user queries
- ⚠️ **Network Security** - Discovery scans broadcast presence; not suitable for hostile networks

### Design Trade-offs

**Why These Decisions:**

1. **ThreadPoolExecutor vs Dask** - Chose simple threading for single-node mode to avoid Dask dependency overhead
2. **JSON Wrapping** - Fallback wrapping sacrifices structure for reliability; ensures pipeline never fails on bad JSON
3. **Synchronous API** - Simpler to reason about; async would improve throughput but add complexity
4. **No Persistent Storage** - Keeps system stateless; easier deployment but loses historical metrics
5. **Fixed Agent Roles** - Researcher/Critic/Editor roles are hardcoded; more flexible but less specialized than dynamic agents
6. **Network Discovery** - Auto-discovery adds convenience but security risk on untrusted networks

### When NOT to Use SynapticLlamas

**This system is NOT suitable for:**
- ❌ **Production Critical Systems** - No HA, no persistence, limited error recovery
- ❌ **Untrusted Networks** - Network discovery is not secure; assumes trusted LAN
- ❌ **Real-time Applications** - Inference can take minutes; not suitable for <1s response times
- ❌ **Highly Concurrent Workloads** - No request queuing; will overwhelm nodes
- ❌ **Sensitive Data** - No encryption in transit; Ollama API is HTTP not HTTPS
- ❌ **Guaranteed Quality** - Output quality varies by model; no SLA on response quality

### When TO Use SynapticLlamas

**This system IS suitable for:**
- ✅ **Research & Experimentation** - Exploring multi-agent architectures and distributed AI
- ✅ **Portfolio Demonstrations** - Showcasing distributed systems, load balancing, adaptive algorithms
- ✅ **Local Development** - Trusted networks, development environments, personal projects
- ✅ **Batch Processing** - Non-urgent queries that can tolerate variable latency
- ✅ **Learning & Education** - Understanding distributed AI orchestration patterns
- ✅ **Prototyping** - Rapid experimentation with multi-agent workflows

### Mitigation Strategies

**For Production Use, Consider:**
- 🔧 Add request queuing (e.g., Celery, Redis Queue)
- 🔧 Implement circuit breakers for node failures (e.g., pybreaker)
- 🔧 Add authentication/authorization (e.g., API keys, JWT)
- 🔧 Use HTTPS reverse proxy for Ollama endpoints
- 🔧 Add persistent storage (SQLite, PostgreSQL) for metrics and state
- 🔧 Implement retry logic with exponential backoff
- 🔧 Add rate limiting per node/user
- 🔧 Use async I/O (asyncio, aiohttp) for better concurrency
- 🔧 Add comprehensive logging and monitoring (Prometheus, Grafana)
- 🔧 Implement health checks with auto-recovery

## Future Enhancements

- Agent-specific memory (JSON/SQLite)
- Web UI dashboard with node monitoring
- Multi-turn conversations with context
- Custom aggregation strategies (LLM-based synthesis)
- Dynamic model selection per agent
- Request queuing and rate limiting
- Async I/O for better concurrency
- Circuit breakers and retry logic
- Authentication and authorization
- Persistent metrics and state
- Prometheus/Grafana integration

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute to this project.

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## License

MIT
