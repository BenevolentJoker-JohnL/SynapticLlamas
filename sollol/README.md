# SOLLOL - Super Ollama Load Balancer

**Intelligent Load Balancing and Distributed Inference for Ollama**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

SOLLOL is a high-performance load balancer and distributed inference engine for Ollama, with support for llama.cpp RPC backends for models that don't fit on a single GPU.

## Features

### 🚀 Core Features
- **Intelligent Load Balancing**: Adaptive routing based on node performance, GPU availability, and task complexity
- **Auto-Discovery**: Automatic detection of Ollama nodes and RPC backends on your network
- **Connection Pooling**: Efficient connection management with health monitoring
- **Request Hedging**: Duplicate requests to multiple nodes for lower latency
- **Task Prioritization**: Priority-based request queuing

### 🔗 Distributed Inference
- **Hybrid Routing**: Automatically routes small models to Ollama, large models to llama.cpp
- **RPC Backend Support**: Connect to llama.cpp RPC servers for distributed inference
- **GGUF Auto-Resolution**: Automatically extracts GGUFs from Ollama blob storage
- **Zero Configuration**: Auto-discovers RPC backends on your network

### 📊 Monitoring & Observability
- **Real-time Metrics**: Track performance, latency, and node health
- **Web Dashboard**: Monitor routing decisions and backend status
- **Performance Learning**: Adapts routing based on historical performance

## Installation

### From PyPI (when published)
```bash
pip install sollol
```

### From Source
```bash
git clone https://github.com/BenevolentJoker-JohnL/SynapticLlamas.git
cd SynapticLlamas/sollol
pip install -e .
```

## Quick Start

### Basic Usage

```python
from sollol import OllamaPool

# Auto-discover Ollama nodes and create pool
pool = OllamaPool.auto_configure()

# Make a chat request
response = pool.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Hello!"}]
)
print(response)
```

### With Distributed Inference

```python
from sollol import HybridRouter, OllamaPool
from sollol.rpc_discovery import auto_discover_rpc_backends

# Discover RPC backends
rpc_backends = auto_discover_rpc_backends()

# Create hybrid router
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    rpc_backends=rpc_backends,
    enable_distributed=True
)

# Routes automatically: small models → Ollama, large models → llama.cpp
response = await router.route_request(
    model="llama3.1:405b",  # Automatically uses distributed inference
    messages=[{"role": "user", "content": "Explain quantum computing"}]
)
```

### Auto-Discovery

```python
from sollol.discovery import discover_ollama_nodes
from sollol.rpc_discovery import auto_discover_rpc_backends

# Discover Ollama nodes
ollama_nodes = discover_ollama_nodes()
print(f"Found {len(ollama_nodes)} Ollama nodes")

# Discover RPC backends for distributed inference
rpc_backends = auto_discover_rpc_backends()
print(f"Found {len(rpc_backends)} RPC backends")
```

## Configuration

### OllamaPool Options

```python
from sollol import OllamaPool

pool = OllamaPool(
    nodes=[
        {"host": "10.9.66.154", "port": "11434"},
        {"host": "10.9.66.157", "port": "11434"}
    ],
    enable_intelligent_routing=True,  # Use smart routing
    exclude_localhost=False  # Include localhost in discovery
)
```

### HybridRouter Options

```python
from sollol import HybridRouter

router = HybridRouter(
    ollama_pool=pool,
    rpc_backends=[
        {"host": "192.168.1.10", "port": 50052},
        {"host": "192.168.1.11", "port": 50052}
    ],
    coordinator_host="127.0.0.1",
    coordinator_port=8080,
    enable_distributed=True,
    auto_discover_rpc=True  # Auto-discover RPC backends
)
```

## Distributed Inference Setup

### 1. Start RPC Servers (Worker Nodes)

On each worker node:
```bash
# Build llama.cpp with RPC support
git clone https://github.com/ggerganov/llama.cpp
cd llama.cpp
cmake -B build -DGGML_RPC=ON -DLLAMA_CURL=OFF
cmake --build build --config Release -j$(nproc)

# Start RPC server
./build/bin/rpc-server --host 0.0.0.0 --port 50052
```

### 2. Use SOLLOL with Auto-Discovery

```python
from sollol import HybridRouter, OllamaPool

# Everything auto-configures!
router = HybridRouter(
    ollama_pool=OllamaPool.auto_configure(),
    enable_distributed=True,
    auto_discover_rpc=True  # Finds RPC servers automatically
)

# Use it
response = await router.route_request(
    model="llama3.1:405b",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

## API Reference

### OllamaPool

**Methods:**
- `chat(model, messages, priority=5, **kwargs)` - Chat completion
- `generate(model, prompt, priority=5, **kwargs)` - Text generation
- `embed(model, input, priority=5, **kwargs)` - Generate embeddings
- `get_stats()` - Get pool statistics
- `add_node(host, port)` - Add a node to the pool
- `remove_node(host, port)` - Remove a node

### HybridRouter

**Methods:**
- `route_request(model, messages, **kwargs)` - Route request to appropriate backend
- `should_use_distributed(model)` - Check if model should use distributed inference
- `get_stats()` - Get routing statistics

### Discovery

**Functions:**
- `discover_ollama_nodes(timeout=0.5)` - Discover Ollama nodes
- `auto_discover_rpc_backends(port=50052)` - Discover llama.cpp RPC backends
- `check_rpc_server(host, port, timeout=1.0)` - Check if RPC server is running

## Environment Variables

- `OLLAMA_HOST` - Default Ollama host (e.g., `http://localhost:11434`)
- `LLAMA_RPC_BACKENDS` - Comma-separated RPC backends (e.g., `192.168.1.10:50052,192.168.1.11:50052`)

## Performance

SOLLOL provides intelligent routing that adapts to:
- **Node Performance**: Routes requests to faster nodes
- **GPU Availability**: Prefers nodes with available GPU memory
- **Task Complexity**: Routes complex tasks to more capable nodes
- **Historical Performance**: Learns from past routing decisions

## Integration with SynapticLlamas

SOLLOL is the load balancing engine that powers [SynapticLlamas](https://github.com/BenevolentJoker-JohnL/SynapticLlamas), a distributed multi-agent AI orchestration platform. While SOLLOL can be used standalone, SynapticLlamas adds:

- Multi-agent orchestration
- Collaborative workflows
- AST-based quality voting
- Interactive CLI
- Web dashboard

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Credits

Part of the [SynapticLlamas](https://github.com/BenevolentJoker-JohnL/SynapticLlamas) project by BenevolentJoker-JohnL.
