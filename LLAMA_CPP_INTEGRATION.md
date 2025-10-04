# llama.cpp Distributed Inference Integration

**FULLY INTEGRATED into SynapticLlamas** ✅

SynapticLlamas now supports TRUE distributed inference using llama.cpp for large models (>70B parameters) that don't fit on a single GPU, while maintaining Ollama compatibility for smaller models.

---

## 🎯 What's Integrated

### 1. **Distributed Inference Engine** (`sollol/hybrid_router.py`)
- Automatic routing between Ollama (small models) and llama.cpp (large models)
- GGUF auto-extraction from Ollama blob storage
- On-demand coordinator creation
- Support for ANY size model

### 2. **Main Application Integration** (`main.py`)
- Full CLI support for distributed inference
- Interactive commands for managing RPC backends
- Persistent configuration storage
- Dashboard monitoring integration

### 3. **Distributed Orchestrator** (`distributed_orchestrator.py`)
- HybridRouter integration
- Automatic GGUF resolution
- Seamless model routing

### 4. **Dashboard Monitoring** (`dashboard_server.py`, `dashboard.html`)
- Real-time llama.cpp backend logs
- Coordinator lifecycle tracking
- RPC backend monitoring
- WebSocket streaming of events

---

## 🚀 Quick Start

### Option 1: Command Line (One-Time Setup)

```bash
# Start with distributed inference enabled
python3 main.py --distributed \
  --enable-distributed-inference \
  --rpc-backend 192.168.1.10:50052 \
  --rpc-backend 192.168.1.11:50052

# Configuration is saved automatically
```

### Option 2: Interactive Mode (Auto-Discovery)

```bash
# Start interactive mode
python3 main.py

# Auto-discover RPC backends on your network
SynapticLlamas> rpc discover
🔍 Scanning network for RPC backends...
   ✅ Found: 192.168.1.10:50052
   ✅ Found: 192.168.1.11:50052
✅ Added 2 new RPC backend(s)

# Or manually add if needed
SynapticLlamas> rpc add 192.168.1.12:50052

# List configured backends
SynapticLlamas> rpc list

# Enable distributed inference
SynapticLlamas> distributed on

# Check status
SynapticLlamas> status
```

---

## 📋 Interactive Commands

### Distributed Inference Management

| Command | Description |
|---------|-------------|
| `distributed on/off` | Enable/disable llama.cpp distributed inference |
| `rpc discover` | **Auto-discover RPC backends on network** |
| `rpc add <host:port>` | Add RPC backend (default port: 50052) |
| `rpc remove <host:port>` | Remove RPC backend |
| `rpc list` | List configured RPC backends |
| `status` | Show distributed inference status |
| `dashboard` | Launch web dashboard with llama.cpp monitoring |

### Dashboard Monitoring

The dashboard includes a dedicated **"llama.cpp Backend"** tab showing:
- 🚀 Coordinator start/stop events
- 📦 Model loading activity
- 🔗 RPC backend connections/disconnections
- ✓ Active backend status
- 📡 Distributed mode indicators

---

## 🔍 Auto-Discovery Feature

**Zero-configuration RPC backend setup!**

SynapticLlamas can automatically discover llama.cpp RPC servers on your network:

### How Auto-Discovery Works

1. **Network Scanning**: Scans local subnet for RPC servers on port 50052
2. **Parallel Detection**: Fast multi-threaded scanning (<1 second)
3. **Automatic Configuration**: Discovered backends are saved to config
4. **Environment Support**: Honors `LLAMA_RPC_BACKENDS` environment variable

### Using Auto-Discovery

**Automatic (on startup)**:
```bash
# Enable distributed inference (triggers auto-discovery if no backends configured)
SynapticLlamas> distributed on
🔍 Distributed inference enabled but no RPC backends configured. Auto-discovering...
✅ Auto-discovered and configured 2 RPC backends
```

**Manual (command)**:
```bash
# Manually scan network for RPC backends
SynapticLlamas> rpc discover
🔍 Scanning network for RPC backends...
   ✅ Found: 192.168.1.10:50052
   ✅ Found: 192.168.1.11:50052
✅ Added 2 new RPC backend(s)
```

**Environment Variable**:
```bash
# Pre-configure backends via environment
export LLAMA_RPC_BACKENDS="192.168.1.10:50052,192.168.1.11:50052"
python3 main.py --distributed
```

---

## 🔧 How It Works

### 1. **Model Size Detection**
```python
# Automatic routing based on model size
if model_size <= 13B:
    # Route to Ollama pool
elif model_size <= 70B:
    # Route to Ollama if available, else distributed
else:
    # Must use distributed (llama.cpp)
```

### 2. **GGUF Auto-Extraction**
```python
# Pull model once with Ollama
ollama pull llama3.1:405b

# SynapticLlamas automatically:
# 1. Finds GGUF in ~/.ollama/models/blobs/
# 2. Extracts and uses it for distributed inference
# 3. No manual file management needed!
```

### 3. **Coordinator Lifecycle**
```python
# On-demand coordinator creation per model
if model == "llama3.1:405b":
    # 1. Resolve GGUF from Ollama
    # 2. Start llama-server coordinator
    # 3. Connect RPC backends
    # 4. Distribute model layers automatically
```

### 4. **Dashboard Monitoring**
```python
# Real-time WebSocket streaming
ws://localhost:8080/ws/llama_cpp_logs

# Events logged:
# - Coordinator lifecycle
# - Model loading/unloading
# - RPC backend changes
# - Active processing status
```

---

## 📊 Architecture

```
┌─────────────────────────────────────────┐
│         SynapticLlamas Main             │
│                                         │
│  DistributedOrchestrator                │
│    ├─ SOLLOLLoadBalancer                │
│    └─ HybridRouter                      │
│         ├─ OllamaPool (small models)    │
│         └─ LlamaCppCoordinator (large)  │
│              ├─ RPC Backend 1           │
│              ├─ RPC Backend 2           │
│              └─ RPC Backend N           │
└─────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────┐
│          Dashboard (Port 8080)          │
│                                         │
│  WebSocket Endpoints:                   │
│   ├─ /ws/dashboard (metrics)            │
│   ├─ /ws/logs (app logs)                │
│   ├─ /ws/ollama_logs (node activity)    │
│   └─ /ws/llama_cpp_logs (backend)       │
└─────────────────────────────────────────┘
```

---

## 🎮 Full Usage Example

### 1. Setup RPC Backends (Worker Nodes)

On each worker node:
```bash
# Build llama.cpp with RPC support
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
GGML_RPC=ON make rpc-server

# Start RPC server
./rpc-server --host 0.0.0.0 --port 50052 --mem 2048
```

### 2. Configure SynapticLlamas (Coordinator Node)

**Option A: Auto-Discovery (Recommended)**
```bash
# Pull model in Ollama
ollama pull llama3.1:405b

# Start SynapticLlamas
python3 main.py --distributed

# Auto-discover RPC backends
SynapticLlamas> rpc discover
SynapticLlamas> distributed on
SynapticLlamas> dashboard
```

**Option B: Manual Configuration**
```bash
# Start SynapticLlamas
python3 main.py --distributed

# In interactive mode:
SynapticLlamas> rpc add 192.168.1.10:50052
SynapticLlamas> rpc add 192.168.1.11:50052
SynapticLlamas> distributed on
SynapticLlamas> dashboard
```

### 3. Launch Dashboard (Monitor Everything)

```bash
# Dashboard automatically shows:
# - Ollama node activity
# - llama.cpp coordinator status
# - RPC backend connections
# - Real-time log streaming

# Open browser: http://localhost:8080
```

### 4. Run Large Model

```bash
SynapticLlamas> Explain quantum computing using llama3.1:405b

# Behind the scenes:
# 1. HybridRouter detects model size (405B)
# 2. Resolves GGUF from Ollama storage
# 3. Starts coordinator with RPC backends
# 4. Distributes model across workers
# 5. Executes inference
# 6. Returns result in Ollama format
```

---

## 🔍 Monitoring & Debugging

### Dashboard Monitoring

The **llama.cpp Backend** tab shows:

```
[10:30:45] [system] 🔌 Connected to llama.cpp monitoring
[10:30:46] [coordinator] 🚀 llama.cpp coordinator started (port 8080)
[10:30:47] [coordinator] 📦 Model loaded: llama3.1:405b
[10:30:48] [rpc_backend] 🔗 RPC backend connected: 192.168.1.10:50052
[10:30:49] [rpc_backend] 🔗 RPC backend connected: 192.168.1.11:50052
[10:31:00] [coordinator] ✓ Coordinator active (2 RPC backends)
```

### Application Logs

```python
# In application logs, you'll see:
INFO - 🔍 Resolving GGUF path for Ollama model: llama3.1:405b
INFO - ✅ Found GGUF: /home/user/.ollama/models/blobs/sha256-abc123...
INFO - 🚀 Starting llama.cpp coordinator for llama3.1:405b...
INFO - ✅ Coordinator started with 2 RPC backends on 127.0.0.1:8080
INFO - 🔗 Routing 'llama3.1:405b' to llama.cpp distributed cluster
```

### Status Check

```bash
SynapticLlamas> status

┌───────────────────────┬─────────────────┐
│ Mode                  │ distributed     │
│ Model                 │ llama3.2        │
│ Distributed Inference │ ON              │
│ RPC Backends          │ 2               │
│ Ollama Nodes          │ 3               │
│ Healthy Nodes         │ 3               │
└───────────────────────┴─────────────────┘
```

---

## 💾 Configuration Storage

All settings are automatically saved to `~/.synapticllamas.json`:

```json
{
  "mode": "distributed",
  "distributed_inference_enabled": true,
  "rpc_backends": [
    {"host": "192.168.1.10", "port": 50052},
    {"host": "192.168.1.11", "port": 50052}
  ],
  "model": "llama3.2",
  "collaborative_mode": false,
  "flockparser_enabled": false
}
```

---

## 🎯 Model Routing Matrix

| Model Size | Backend | Why |
|------------|---------|-----|
| ≤ 13B (llama3.2, phi3) | Ollama Pool | Fits on single GPU, fast |
| 14B-70B (llama2:70b) | Ollama or llama.cpp | Depends on availability |
| > 70B (llama3.1:405b) | llama.cpp Distributed | Required for large models |

**Automatic routing - no manual configuration needed!**

---

## 🚨 Troubleshooting

### Issue: "No RPC backends configured"
```bash
# Add backends first
SynapticLlamas> rpc add 192.168.1.10:50052
SynapticLlamas> distributed on
```

### Issue: "Could not find GGUF for model"
```bash
# Pull model in Ollama first
ollama pull llama3.1:405b

# Then use in SynapticLlamas
SynapticLlamas> Explain quantum computing
```

### Issue: "Coordinator unhealthy"
```bash
# Check RPC servers are running
curl http://192.168.1.10:50052/health

# Restart RPC server
./rpc-server --host 0.0.0.0 --port 50052 --mem 2048
```

---

## 🎉 Summary

**llama.cpp distributed inference is FULLY INTEGRATED into SynapticLlamas!**

✅ **Zero configuration** - Auto-discovers RPC backends on your network
✅ **Works out of the box** - Just enable distributed inference
✅ **Zero manual GGUF management** - Auto-extracts from Ollama
✅ **Automatic routing** - Small → Ollama, Large → Distributed
✅ **Full monitoring** - Dashboard with real-time logs
✅ **Persistent config** - Settings saved automatically
✅ **CLI + Interactive** - Both modes fully supported

**You can now run ANY size model with the Ollama API - no manual setup!** 🚀
