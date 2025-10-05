# SOLLOL - Hybrid Cluster Orchestrator for Local LLMs

**The first open-source orchestration layer that unifies task routing and distributed model inference for local LLM clusters.**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

SOLLOL (Super Ollama Load balancer & Orchestration Layer) is a production-ready cluster orchestrator designed specifically for local LLM deployments. It intelligently manages both **task-level parallelism** (distributing agent tasks across nodes) and **model-level parallelism** (sharding large models across RPC backends).

---

## 🎯 What Makes SOLLOL Unique

**Existing solutions force you to choose:**
- Ray/vLLM: Enterprise complexity, cloud-first design
- Petals: P2P over Internet, unreliable for local clusters
- llama.cpp RPC: Low-level protocol, no orchestration
- Ollama: Single-node only, no distribution

**SOLLOL gives you everything:**

```
┌─────────────────────────────────────────────────────────┐
│          SOLLOL Hybrid Orchestration Layer              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  🎯 HybridRouter (Intelligent Mode Selection)          │
│       ├→ Task Distribution: Parallel agent tasks       │
│       │   across Ollama nodes (horizontal scaling)     │
│       └→ Model Sharding: Single large model split      │
│           across llama.cpp RPC backends (vertical)     │
│                                                         │
│  📊 Production Features:                               │
│    • Health monitoring & auto-recovery                 │
│    • Real-time dashboard with RPC logs                 │
│    • Systemd service management                        │
│    • Auto-discovery (Ollama + RPC backends)            │
│    • Ollama API compatibility (drop-in replacement)    │
└─────────────────────────────────────────────────────────┘
```

**Key Innovation:** SOLLOL is the **first system** that combines task routing and model sharding in a **homelab-friendly package** with production-ready features.

---

## 🚀 Quick Start

### Installation

```bash
# Clone SynapticLlamas
git clone https://github.com/BenevolentJoker-JohnL/SynapticLlamas.git
cd SynapticLlamas

# Install
pip install -e .
```

### Setup RPC Backend Services (One-time setup per node)

On each node in your cluster:

```bash
# Install SOLLOL RPC service (systemd)
cd SynapticLlamas/SOLLOL
./scripts/install-rpc-service.sh

# Service auto-starts and runs on boot
systemctl --user status sollol-rpc-server
```

### Configure SynapticLlamas

Edit `~/.synapticllamas.json`:

```json
{
  "model_sharding_enabled": true,
  "task_distribution_enabled": false,
  "rpc_backends": [
    {"host": "10.9.66.154", "port": 50052},
    {"host": "10.9.66.157", "port": 50052},
    {"host": "10.9.66.45", "port": 50052}
  ]
}
```

### Run!

```bash
cd SynapticLlamas
python3 main.py
```

Now queries automatically use distributed model sharding:

```
SynapticLlamas> explain quantum computing

🚀 Command: llama-server --model codellama:13b --rpc 10.9.66.154:50052,10.9.66.157:50052,10.9.66.45:50052
   ⏳ Loading model across RPC backends...
   📊 load_tensors: RPC0[10.9.66.154:50052] model buffer size = 2.3 GiB (layers 0-13)
   📊 load_tensors: RPC1[10.9.66.157:50052] model buffer size = 2.3 GiB (layers 14-27)
   📊 load_tensors: RPC2[10.9.66.45:50052] model buffer size = 2.3 GiB (layers 28-40)
   ✅ Model loaded and ready
   ✅ Researcher completed in 149.78s
```

---

## 🏗️ Architecture

### Dual Operating Modes

#### Mode 1: Model Sharding (`model_sharding_enabled: true`)
**Use case:** Run models too large for a single node

- Splits model **layers** across RPC backends
- Each backend holds ~1/N of the model
- Coordinated by llama-server
- Automatic layer distribution

**Example:** 70B model across 3x 24GB nodes
- Node 1: Layers 0-26 (~23GB)
- Node 2: Layers 27-53 (~23GB)
- Node 3: Layers 54-80 (~23GB)

#### Mode 2: Task Distribution (`task_distribution_enabled: true`)
**Use case:** Parallel agent workflows

- Distributes **tasks** across Ollama nodes
- Each node runs full model
- Parallel execution of independent agents
- Load balancing with health checks

**Example:** 5 research agents on 3 nodes
- Node 1: Agents #1, #4
- Node 2: Agents #2, #5
- Node 3: Agent #3

#### Hybrid Mode (Both enabled)
SOLLOL intelligently routes based on task:
- Large models → RPC sharding
- Small parallel tasks → Ollama distribution

---

## 📊 Features

### Core Orchestration
- ✅ **HybridRouter**: Intelligent mode selection
- ✅ **Health Monitoring**: Per-backend health tracking with exponential backoff
- ✅ **Auto-Discovery**: Network scanning for Ollama nodes + RPC backends
- ✅ **GGUF Resolution**: Automatic extraction from Ollama blob storage
- ✅ **Connection Pooling**: Efficient HTTP client management

### Production Features
- ✅ **Systemd Services**: Install RPC servers as persistent services
- ✅ **Real-time Dashboard**: Web UI with RPC distribution logs (port 8080)
- ✅ **Metrics & Telemetry**: Request latency, success rates, throughput
- ✅ **Auto-Recovery**: Failed nodes removed from rotation, auto-rejoin on health
- ✅ **Configuration Persistence**: Settings saved to `~/.synapticllamas.json`

### Developer Experience
- ✅ **Ollama API Compatibility**: Drop-in replacement
- ✅ **Python SDK**: Clean async/sync APIs
- ✅ **CLI Tools**: Interactive shell for cluster management
- ✅ **Logging**: Structured logging with coordinator stdout streaming

---

## 🔧 Configuration Reference

### Full Configuration File (`~/.synapticllamas.json`)

```json
{
  "mode": "distributed",
  "collaborative_mode": true,
  "refinement_rounds": 1,
  "agent_timeout": 300,

  "model_sharding_enabled": true,
  "task_distribution_enabled": false,

  "rpc_backends": [
    {"host": "10.9.66.154", "port": 50052},
    {"host": "10.9.66.157", "port": 50052},
    {"host": "10.9.66.45", "port": 50052}
  ],

  "model": "codellama:13b",
  "quality_threshold": 0.9,
  "ast_voting_enabled": true
}
```

### Environment Variables

```bash
# llama-server path (auto-detected if not set)
export LLAMA_SERVER_PATH=/path/to/llama.cpp/build/bin/llama-server

# Dashboard port (default: 8080)
export SOLLOL_DASHBOARD_PORT=8080
```

---

## 🎯 Use Cases

### 1. Large Model Inference (70B+)
**Problem:** Model doesn't fit on single GPU
**Solution:** Model sharding across 3-4 consumer GPUs

```json
{
  "model_sharding_enabled": true,
  "task_distribution_enabled": false,
  "rpc_backends": [
    {"host": "192.168.1.10", "port": 50052},
    {"host": "192.168.1.11", "port": 50052},
    {"host": "192.168.1.12", "port": 50052}
  ]
}
```

### 2. Multi-Agent Workflows
**Problem:** 10 research agents need to run in parallel
**Solution:** Task distribution across Ollama cluster

```json
{
  "model_sharding_enabled": false,
  "task_distribution_enabled": true
}
```

### 3. Hybrid Production Cluster
**Problem:** Need both large models AND parallel tasks
**Solution:** Enable both modes, let HybridRouter decide

```json
{
  "model_sharding_enabled": true,
  "task_distribution_enabled": true
}
```

---

## 🔬 How It Works

### RPC Model Sharding Flow

1. **User Query** → SynapticLlamas orchestrator
2. **HybridRouter** detects model size > threshold → route to RPC
3. **GGUF Resolution** extracts model from Ollama storage
4. **Coordinator Start** llama-server with `--rpc backend1,backend2,backend3`
5. **Automatic Distribution** llama-server splits layers across backends
6. **Inference** queries coordinated across backends
7. **Cleanup** coordinator stops, backends remain ready

### Health Monitoring

- **Initial Check**: TCP connection test on backend registration
- **Cached Status**: 5-minute cache to avoid overwhelming RPC servers
- **Failure Detection**: Backends removed on repeated failures
- **Auto-Recovery**: Periodic re-checks restore healthy backends

**Why 5-minute cache?** RPC servers have tiny connection backlogs (often just 2). Active coordinator connections fill the queue, making health checks impossible. We assume backends stay healthy after initial verification.

---

## 📚 API Reference

### Python SDK

```python
from sollol import HybridRouter, RPCBackend

# Create router
router = HybridRouter(
    rpc_backends=[
        RPCBackend(host="10.9.66.154", port=50052),
        RPCBackend(host="10.9.66.157", port=50052)
    ],
    enable_distributed=True
)

# Generate with automatic routing
response = await router.generate(
    model="codellama:13b",
    messages=[{"role": "user", "content": "Explain neural networks"}]
)
```

### REST API (Gateway Mode)

```bash
# Start gateway on port 11434 (Ollama compatible)
python -m sollol.serve --port 11434

# Use standard Ollama API
curl http://localhost:11434/api/chat -d '{
  "model": "codellama:13b",
  "messages": [{"role": "user", "content": "Hello"}]
}'
```

---

## 🐛 Troubleshooting

### RPC Backend Shows "Offline" But Is Running

**Cause:** Coordinator holding persistent connections fills the small backlog
**Expected:** This is normal! "Offline" status during inference means backend is **busy working**
**Solution:** Status will return to "healthy" after coordinator releases connections

### Model Loading Takes 5+ Minutes

**Cause:** Multi-backend model loading is slower than single-node
**Expected:** 2-5 minutes for 13B, 5-10 minutes for 70B
**Solution:** Increase timeout in config or wait longer

### "Connection Refused" Errors

**Check:**
1. RPC services running: `systemctl --user status sollol-rpc-server`
2. Firewall allows port 50052
3. Correct IP addresses in config
4. Test connectivity: `nc -zv <host> 50052`

---

## 🤝 Contributing

We welcome contributions! Areas of interest:

- [ ] Automatic model-size routing thresholds
- [ ] GPU memory-aware backend selection
- [ ] Pipeline parallelism support
- [ ] Ray integration for hybrid Ray+RPC clusters
- [ ] Kubernetes operator

---

## 📄 License

MIT License - see [LICENSE](../LICENSE)

---

## 🔗 Links

- **SynapticLlamas**: [Main Project](../)
- **Dashboard**: http://localhost:8080 (when running)
- **Issues**: [GitHub Issues](https://github.com/BenevolentJoker-JohnL/SynapticLlamas/issues)
