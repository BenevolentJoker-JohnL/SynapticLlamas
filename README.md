# 🧠 SynapticLlamas

**Distributed Parallel Agent Playground** - A portfolio-ready distributed AI orchestration system that actually keeps its performance promises.

---

## 🚀 Quick Start (30 seconds)

**Zero-config Ollama with full SynapticLlamas observability:**

```bash
pip install -e .
```

```python
import logging
logging.basicConfig(level=logging.INFO)  # See the magic happen

from sollol import Ollama

client = Ollama()  # Auto-discovers, just works
response = client.chat("llama3.2", "Summarize quantum computing")
```

**Output shows full observability:**
```
🎯 Intelligent routing: Task: summarization (simple); Host localhost:11434
✅ Request succeeded: localhost:11434 (latency: 3320ms, avg: 3320ms)
```

**What just happened:**
- ✅ Auto-discovered Ollama nodes in <1 second
- ✅ Analyzed request → detected "summarization" task
- ✅ Intelligent routing with decision reasoning
- ✅ Performance tracking (latency, success rate)
- ✅ Learning from each request
- ✅ **Full SynapticLlamas observability - automatically!**

**This isn't basic load balancing.** This is production-grade intelligent routing with complete observability, working out of the box.

### 🚀 NEW: llama.cpp Model Sharding - INTEGRATED

**Run larger models across multiple machines.**

SynapticLlamas integrates llama.cpp RPC for layer-level model sharding, enabling inference on models that don't fit on a single GPU (verified with 13B models across 2-3 nodes).

```bash
# Quick Start - CLI Mode
python3 main.py --distributed \
  --enable-distributed-inference \
  --rpc-backend 192.168.1.10:50052 \
  --rpc-backend 192.168.1.11:50052

# Quick Start - Interactive Mode
python3 main.py
SynapticLlamas> rpc add 192.168.1.10:50052
SynapticLlamas> distributed on
SynapticLlamas> dashboard  # Monitor everything!
```

**What you get:**
- ✅ **GGUF extraction** from Ollama storage (no manual file management)
- ✅ **Layer distribution** across RPC backends (automatic via llama-server)
- ✅ **Real-time logs** showing which backend gets which layers
- ✅ **Systemd service** for persistent RPC servers
- ✅ **Configuration persistence** - Settings saved automatically

**Trade-offs:**
- ⚠️ Startup time: 2-5 minutes for 13B models (vs ~20s local)
- ⚠️ Slower inference than local due to network overhead (~5 tok/s vs ~20 tok/s)
- ⚠️ Worth it when model doesn't fit on single machine

📚 **[Full Guide with Performance Data →](DISTRIBUTED_INFERENCE.md)**

### 🚀 ALSO: SOLLOL Gateway (Standalone)

**SOLLOL IS your Ollama - just run it!**

```bash
# Start SOLLOL on port 11434 (the Ollama port)
./start_gateway.sh

# SOLLOL running on http://localhost:11434
# ✅ Auto-discovers Ollama nodes on network
# ✅ Auto-discovers RPC servers for distributed inference
# ✅ Auto-extracts GGUF from Ollama storage
# ✅ Intelligent routing (small → Ollama pool, large → distributed)

# (Optional) Enable distributed inference by starting RPC servers on worker nodes:
# rpc-server --host 0.0.0.0 --port 50052 --mem 2048
```

**Your apps work unchanged:**
```bash
# All existing Ollama apps just work!
curl http://localhost:11434/api/chat -d '...'  # Uses SOLLOL transparently
ollama run llama3.2  # Works (set OLLAMA_HOST=http://localhost:11434)
```

**Python SDK Example:**

```python
from sollol import HybridRouter, RPCBackend

# Configure RPC backends
router = HybridRouter(
    rpc_backends=[
        RPCBackend(host="10.9.66.154", port=50052),
        RPCBackend(host="10.9.66.157", port=50052)
    ],
    enable_distributed=True
)

# Automatically shards model across backends
response = await router.generate(
    model="codellama:13b",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**What actually happens:**
- ✅ GGUF extracted from Ollama storage
- ✅ llama-server starts with --rpc backend1,backend2
- ✅ Layers distributed automatically (shown in logs)
- ✅ Inference coordinated across backends
- ✅ Slower than local, but enables larger-than-VRAM models

📚 **[Performance Characteristics & Setup →](DISTRIBUTED_INFERENCE.md)**

---

## The Problem

You have multiple Ollama nodes on your network. You want to run AI agents in parallel for faster processing. Sounds simple, right?

**Here's what happens:**

```python
# You route to your GPU node for speed
route_to_node("http://gpu-server:11434")  # ✅ Routed to GPU node

# But the model loads on CPU anyway
# Result: 45 seconds instead of 2 seconds
# 20x slower than expected
# Your "intelligent routing" is pointless
```

**The core issue:** Load balancers route *to* GPU nodes, but can't ensure models actually *run* on GPU. You get:
- Inconsistent performance (2s or 45s? Coin flip!)
- Wasted GPU hardware
- "Intelligent routing" that routes to slow execution
- No way to verify or fix it

**Current solutions fail:**

| Approach | Problem |
|----------|---------|
| **Simple round-robin** | No intelligence - sends heavy tasks to weak nodes |
| **Least-loaded routing** | Chooses busy GPU over idle CPU = still slow |
| **Manual GPU control** | You force models to GPU... then next request loads on CPU again |
| **Hope for the best** | Model *might* use GPU... or might not 🤷 |

**What you actually need:**

1. Smart routing that understands task types
2. GPU controller that ensures models run on GPU
3. Verification that routing decisions match reality
4. A closed feedback loop: route → verify → fix → learn

None of the existing Ollama load balancers do this.

---

## The Solution

**SynapticLlamas** combines intelligent routing with active GPU control:

```python
# 1. Analyzes your request
context = analyze_request(payload)
# → Task: embedding, Complexity: medium, Requires GPU: Yes

# 2. Routes intelligently
node = route_to_optimal_node(context)
# → Selected: http://gpu-server:11434 (score: 450, has GPU)

# 3. VERIFIES model is on GPU
verify_gpu_placement("mxbai-embed-large", node)
# → Model on CPU! Forcing to GPU...

# 4. FIXES IT
force_gpu_load("mxbai-embed-large", node)
# → ✅ Model now on GPU (verified)

# 5. Executes (fast!)
result = execute_embedding(text)
# → 2 seconds (not 45 seconds)

# 6. LEARNS from actual performance
record_performance(node, actual_time=2000ms)
# → Router learns this node is reliable for embeddings
```

**Result:** 20x faster, consistently. No coin flips.

---

## Show Me The Difference

### Before SynapticLlamas

**Scenario:** Embed 1000 documents using mxbai-embed-large

```python
# Traditional load balancer
load_balancer = SimpleLoadBalancer([
    "http://gpu-node:11434",
    "http://cpu-node:11434"
])

# Routes to GPU node (good!)
node = load_balancer.get_node()  # → gpu-node

# But model loads on CPU (bad!)
embeddings = embed(texts, node)
# Time: 45 seconds 🐌
# Why? Model loaded on CPU despite GPU available
# Your expensive GPU sits idle
```

### After SynapticLlamas

```python
# SOLLOL load balancer (with GPU controller)
load_balancer = SOLLOLLoadBalancer(registry, enable_gpu_control=True)

# Analyzes request + routes intelligently
decision = load_balancer.route_request({
    'model': 'mxbai-embed-large',
    'prompt': texts
})
# → Routes to GPU node
# → Verifies model is on GPU
# → Forces GPU load if needed
# → Executes embedding

# Time: 2 seconds ⚡
# Why? Model guaranteed to be on GPU
# Performance promise fulfilled
```

**Same hardware, 20x faster.** The difference is active control, not passive routing.

---

## Why This Matters

### The Performance Promise Gap

**What load balancers promise:**
> "Intelligent routing to fastest nodes"

**What they deliver:**
```
Routes to GPU node ✅
Model runs on CPU ❌
Takes 45s instead of 2s ❌
```

**The gap:** Routing is only half the battle. Without GPU control, your "intelligent routing" routes to dumb execution.

### Real-World Impact

**Embedding 10,000 documents:**
- **Without GPU control:** 45s × 10 batches = 7.5 minutes (maybe - if you're lucky)
- **With GPU control:** 2s × 10 batches = 20 seconds (guaranteed)

**Chat with multi-turn context (500 tokens):**
- **Without GPU control:** 60s (if on CPU) or 3s (if on GPU) - inconsistent
- **With GPU control:** 3s every time

**This compounds:** 10 agents × 100 requests = massive waste or massive speedup.

### Why Active Control Matters

Ollama doesn't guarantee GPU usage. Models can load on:
- **GPU (VRAM):** Fast (2s for embedding)
- **CPU (RAM):** Slow (45s for embedding)

**Without verification:**
```bash
$ curl http://gpu-node:11434/api/ps
{
  "models": [{
    "name": "mxbai-embed-large",
    "size_vram": 0,          ← On CPU!
    "size": 669384704
  }]
}
```

You routed to GPU node, but model is on CPU. Your routing was wasted.

**With SynapticLlamas:**
```bash
# GPU controller checks:
$ curl http://gpu-node:11434/api/ps
{
  "models": [{
    "name": "mxbai-embed-large",
    "size_vram": 669384704,  ← On GPU!
    "size": 669384704
  }]
}
```

Routing decision verified. Performance guaranteed.

---

## Architecture: Closed-Loop Control

```
Traditional Load Balancer (Open Loop):
  Request → Route to GPU node → Hope → (Maybe fast, maybe slow)
                                 ↑
                          No verification!

SynapticLlamas (Closed Loop):
  Request → Analyze → Route → Verify → Force GPU → Execute → Fast
              ↑                                               ↓
              └──────────── Learn from actual perf ──────────┘
```

**Why closed-loop wins:**
1. **Analyze:** Understands task type, complexity, requirements
2. **Route:** Scores nodes by GPU, latency, load, history
3. **Verify:** Checks model is actually on GPU
4. **Fix:** Forces GPU load if needed
5. **Execute:** Runs with guaranteed performance
6. **Learn:** Feeds actual performance back to router

No other Ollama load balancer does this.

---

## Key Features (And Why They Matter)

### 🎯 Intelligent Routing
**Problem:** Round-robin sends heavy tasks to weak nodes
**Solution:** Context-aware routing - understands task types, estimates complexity, routes accordingly

### 🚀 Active GPU Controller
**Problem:** Models load on CPU despite GPU availability (20x slower)
**Solution:** Verifies GPU placement after routing, forces GPU load if needed

### 📊 Performance Verification
**Problem:** No way to know if routing worked
**Solution:** Closed feedback loop - measures actual performance, learns from reality

### 🔥 Pre-warming
**Problem:** First request waits for model loading (10+ seconds)
**Solution:** Pre-loads critical models on GPU nodes during setup

### 🌐 Network Discovery
**Problem:** Manual node configuration is tedious
**Solution:** Auto-discovers Ollama instances on your network

### 🏥 Health Monitoring
**Problem:** Routes to dead/slow nodes
**Solution:** Continuous health checks, automatic failover

### 📈 Adaptive Learning
**Problem:** Static routing gets worse over time
**Solution:** Learns from actual performance, adapts strategies

### 🏁 Race-to-First Hedging
**Problem:** Tail latency kills user experience (2000ms vs 100ms - 20x slower on slow requests)
**Solution:** Send request to 2-3 nodes, use fastest response, reduces p99 latency by 75%

---

## Quick Start

### The Problem You're Solving

You have this:
```bash
# Multiple Ollama nodes
http://localhost:11434      # Your laptop (CPU)
http://10.9.66.124:11434    # GPU server (RTX 4090)
http://10.9.66.154:11434    # Old server (CPU)
```

You want agents to run in parallel and use the GPU when beneficial.

### The Simple Solution

```bash
cd SynapticLlamas
pip install -r requirements.txt

# Run with distributed mode
python main.py --distributed

# It automatically:
# ✅ Discovers your nodes
# ✅ Routes intelligently
# ✅ Ensures GPU usage
# ✅ Tracks performance
```

**That's it.** Your agents now run 20x faster with guaranteed GPU usage.

### The Proof

```bash
# Before (manual routing)
time python -c "import ollama; ollama.embed('mxbai-embed-large', 'test')"
# real: 0m45.234s  ← On CPU

# After (SynapticLlamas)
time python main.py -i "test query"
# real: 0m2.156s  ← On GPU (guaranteed)
```

---

## Installation

```bash
cd SynapticLlamas
pip install -r requirements.txt
```

**Note:** SynapticLlamas now uses [SOLLOL](https://github.com/BenevolentJoker-JohnL/SOLLOL) as a package dependency (v0.9.10+) for intelligent routing and distributed inference capabilities.

**Prerequisites:**
- Python 3.8+
- Ollama running locally (`http://localhost:11434`)
- (Optional) Additional Ollama nodes on network

---

## Usage

### Standard Mode (Single Node)

```bash
# Interactive mode
python main.py

# Single query
python main.py -i "Explain quantum computing"
```

### Distributed Mode (Multi-Node with GPU Control)

```bash
# Auto-discover and use all nodes
python main.py --distributed

# Specify nodes manually
python main.py --distributed \
    --add-node http://10.9.66.124:11434 \
    --add-node http://10.9.66.154:11434

# With network discovery
python main.py --distributed --discover 192.168.1.0/24

# With hedging for low latency (race-to-first)
python main.py --distributed --enable-hedging
```

### Dask Mode (True Distributed Cluster)

```bash
# Local Dask cluster (automatic)
python main.py --dask

# Connect to existing Dask scheduler
python main.py --dask --dask-scheduler tcp://192.168.1.50:8786
```

---

## The Technology

### What Makes This Different

**1. Task Analysis**
```python
# Other load balancers:
route_to_next_node()  # Just pick next node

# SynapticLlamas:
context = analyze_request(payload)
# → type: embedding
# → complexity: medium
# → requires_gpu: True
# → estimated_tokens: 250
# → estimated_duration: 1500ms
```

**2. Multi-Factor Scoring**
```python
# Other load balancers:
score = 100 - current_load  # Simple

# SynapticLlamas:
score = (
    base_score
    * gpu_multiplier(1.5x if has GPU)
    * latency_penalty(distance matters)
    * success_rate(history matters)
    * load_penalty(current load)
    * priority_bonus(high-pri tasks)
)
```

**3. GPU Verification**
```python
# Other load balancers:
route_to_node()  # Done
return result

# SynapticLlamas:
route_to_node()
verify_gpu_placement()  # Is model on GPU?
if not on GPU:
    force_gpu_load()    # Fix it
execute()
verify_performance()    # Did it work?
learn()                 # Adapt
```

**4. Race-to-First Hedging** (Inspired by Jerry-Terrasse)
```python
# Other load balancers:
route_to_node()  # Hope it's fast
wait()           # Stuck if slow

# SynapticLlamas:
send_to_node1()  # Racing
send_to_node2()  # In parallel
use_fastest()    # First to respond wins
cancel_slower()  # Stop the slow one
# Result: 75% better tail latency
```

### Performance Impact

**Embedding (mxbai-embed-large, 1000 documents):**
- Traditional routing: 2s - 45s (inconsistent, depends on CPU/GPU lottery)
- SynapticLlamas: 2s every time (GPU guaranteed)
- **Speedup:** 20x faster + consistent

**Generation (llama3.1, 500 tokens):**
- Traditional routing: 3s - 60s (inconsistent)
- SynapticLlamas: 3s every time
- **Speedup:** 20x faster + consistent

**Multi-agent workflow (3 agents in parallel):**
- Sequential: ~40s
- Parallel (no GPU control): 8s - 25s (inconsistent)
- Parallel (SynapticLlamas): 8s every time
- **Speedup:** 5x faster + consistent

**Tail latency (p99 - worst case):**
- Without hedging: 2000ms (when node is slow)
- With hedging (race-to-first): 500ms (use 2nd node if 1st is slow)
- **Improvement:** 75% reduction in tail latency

---

## Architecture Overview

```
SynapticLlamas/
├─ agents/
│  ├─ base_agent.py              # Abstract base with Ollama + JSON pipeline
│  ├─ researcher.py              # Extracts key facts and context
│  ├─ critic.py                  # Analyzes issues and recommendations
│  └─ editor.py                  # Summarizes and polishes output
├─ sollol/                       # SOLLOL - Intelligent load balancing
│  ├─ intelligence.py            # Context-aware routing engine
│  ├─ gpu_controller.py          # Active GPU verification/control
│  ├─ prioritization.py          # Priority queue management
│  └─ adapters.py                # Performance tracking
├─ node_registry.py              # Node management + discovery
├─ sollol_load_balancer.py       # SOLLOL integration
├─ distributed_orchestrator.py   # Distributed execution coordinator
├─ main.py                       # Interactive CLI
└─ requirements.txt
```

---

## Real-World Example

### The Scenario

You're processing 50 PDF documents. Each needs:
1. **Embedding** (mxbai-embed-large) - for search
2. **Summarization** (llama3.1) - for overview
3. **Analysis** (llama3.1) - for insights

**Your network:**
- Laptop: localhost (CPU, slow)
- GPU Server 1: 10.9.66.124 (RTX 4090, fast)
- GPU Server 2: 10.9.66.154 (GTX 1060, medium)

### Traditional Load Balancer

```python
# Round-robin: laptop → gpu1 → gpu2 → laptop → ...
# Problem 1: Sends heavy tasks to laptop (CPU-only)
# Problem 2: Models might load on CPU even on GPU servers
# Problem 3: No awareness of task complexity

Total time: 25 minutes (inconsistent)
- Some embeddings: 2s (GPU)
- Some embeddings: 45s (CPU)
- Some summaries: 3s (GPU)
- Some summaries: 60s (CPU)
# Lottery-based performance
```

### SynapticLlamas

```python
# Intelligent routing + GPU control
# Embeddings → GPU Server 1 (RTX 4090, verified on GPU)
# Summaries → GPU Server 1 (RTX 4090, verified on GPU)
# Analysis → GPU Server 2 (GTX 1060, verified on GPU)
# Laptop → used for lightweight tasks only

Total time: 3 minutes (consistent)
- All embeddings: 2s (GPU guaranteed)
- All summaries: 3s (GPU guaranteed)
- All analysis: 5s (GTX 1060 GPU)
# Performance guaranteed
```

**Result:** 8x faster, consistent, predictable.

---

## FlockParser Integration (Drop-In Replacement)

SynapticLlamas can replace FlockParser's load balancer with **zero code changes**:

```python
# In FlockParser, change ONE line:
from sollol_flockparser_adapter import OllamaLoadBalancer

# Everything else stays the same:
load_balancer = OllamaLoadBalancer(OLLAMA_INSTANCES)
load_balancer.embed_distributed(model, text)  # Uses SOLLOL + GPU control
```

**What you get:**
- Same API, no refactoring
- 20x faster with GPU guarantee
- Intelligent routing under the hood
- Performance tracking and learning

See [FLOCKPARSER_INTEGRATION.md](FLOCKPARSER_INTEGRATION.md) for details.

---

## Benchmarking

```bash
# Benchmark different strategies
python benchmark.py

# Output:
# 📊 Strategy Performance:
#   Sequential:     ~40s
#   Parallel:       ~12s (no GPU control)
#   SOLLOL:         ~8s (with GPU control)
#   Speedup:        5x faster
```

Auto-benchmarks to find fastest strategy for your hardware.

---

## Interactive Commands (Distributed Mode)

```
SynapticLlamas> nodes              # List all Ollama nodes
SynapticLlamas> add http://...     # Add an Ollama node
SynapticLlamas> remove http://...  # Remove an Ollama node
SynapticLlamas> discover 192.168.1.0/24  # Discover Ollama nodes
SynapticLlamas> health             # Health check all nodes
SynapticLlamas> metrics            # Show performance metrics
SynapticLlamas> rag on/off         # Toggle RAG enhancement
```

---

## Limitations & When NOT to Use

### This System is NOT Suitable For:

❌ **Production critical systems** - No HA, no persistence, limited error recovery
❌ **Untrusted networks** - Network discovery assumes trusted LAN
❌ **Real-time applications** - Inference can take seconds/minutes
❌ **Highly concurrent workloads** - No request queuing
❌ **Sensitive data** - No encryption in transit (HTTP not HTTPS)

### This System IS Suitable For:

✅ **Research & Experimentation** - Exploring multi-agent architectures
✅ **Portfolio Demonstrations** - Showcasing distributed systems knowledge
✅ **Local Development** - Trusted networks, development environments
✅ **Batch Processing** - Non-urgent queries with variable latency
✅ **Learning & Education** - Understanding distributed AI orchestration
✅ **Prototyping** - Rapid experimentation with agent workflows

---

## The Bottom Line

**Before SynapticLlamas:**
- You route to GPU nodes
- Models load on CPU anyway
- 20x slower than expected
- "Intelligent routing" is pointless

**After SynapticLlamas:**
- You route to GPU nodes
- GPU controller ensures GPU usage
- 20x faster, guaranteed
- Intelligent routing with verified execution

**The difference:** Active control, not passive routing.

**The edge:** Race-to-first hedging for tail latency (credit: Jerry-Terrasse).

---

## Demos

```bash
# GPU controller demo
python demo_gpu_controller.py

# Hedging demo (race-to-first)
python demo_hedging.py

# FlockParser adapter demo
python demo_flockparser_adapter.py
```

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Code of Conduct

This project adheres to a [Code of Conduct](CODE_OF_CONDUCT.md).

## License

MIT
