# SOLLOL Architecture

## What SOLLOL Actually Is

**SOLLOL is a hybrid cluster orchestrator for local LLM deployments.**

It manages two independent but complementary distribution strategies:

1. **Model Sharding** (llama.cpp RPC): Split large model layers across nodes
2. **Task Distribution** (Ollama Pool): Run parallel agent tasks across nodes

## Core Components

### 1. HybridRouter
Central routing logic that decides between Ollama and llama.cpp based on configuration.

```python
# Routes to appropriate backend
if model_sharding_enabled and has_rpc_backends:
    → LlamaCppCoordinator
elif task_distribution_enabled and has_ollama_nodes:
    → OllamaPool
```

### 2. LlamaCppCoordinator
Manages ephemeral llama-server coordinators for RPC model sharding.

**What it does:**
- Extracts GGUF from Ollama blob storage
- Starts llama-server with `--rpc backend1,backend2,backend3`
- llama-server automatically distributes layers across RPC backends
- Streams coordinator logs to show layer distribution
- Cleans up after inference completes

**Limitations:**
- Coordinator startup: 2-5 minutes for 13B, potentially longer for 70B+
- Only works with models that have GGUF files in Ollama storage
- Requires manual RPC server setup on each node (systemd service)

### 3. RPCBackendRegistry
Tracks RPC backend health and metrics.

**Key insight:** RPC servers have tiny connection backlogs (often 2). Active coordinators fill these queues, making health checks fail even when working perfectly. Solution: 5-minute cache assumes backends stay healthy.

### 4. OllamaPool (Task Distribution)
Connection pool for parallel task execution across Ollama nodes.

**What it does:**
- Load balances agent tasks across multiple Ollama instances
- Each node runs complete model
- Parallel execution for multi-agent workflows

**When to use:** Multiple independent tasks, not large single models.

### 5. DistributedOrchestrator
Main orchestration layer for SynapticLlamas multi-agent workflows.

**Key change:** Only creates OllamaPool if `task_distribution_enabled=true`. Otherwise routes everything through llama.cpp RPC.

## Configuration Model

```json
{
  "model_sharding_enabled": true|false,
  "task_distribution_enabled": true|false,
  "rpc_backends": [
    {"host": "10.9.66.154", "port": 50052}
  ]
}
```

### Mode Matrix

| Model Sharding | Task Distribution | Behavior |
|---------------|-------------------|----------|
| `false` | `false` | Single node only (Ollama or llama.cpp) |
| `true` | `false` | All queries → RPC sharding |
| `false` | `true` | All queries → Ollama pool |
| `true` | `true` | HybridRouter decides per-request |

## Data Flow

### Model Sharding Flow (RPC)

```
User Query
  ↓
HybridRouter
  ↓
OllamaGGUFResolver (extract GGUF from blob storage)
  ↓
LlamaCppCoordinator
  ↓
Start llama-server --rpc backend1,backend2,backend3
  ↓
llama-server distributes layers automatically
  ↓
Inference across backends
  ↓
Stop coordinator, backends remain ready
```

### Task Distribution Flow (Ollama)

```
Multiple Agent Tasks
  ↓
HybridRouter
  ↓
OllamaPool (load balancer)
  ↓
Distribute tasks across N Ollama nodes
  ↓
Parallel execution
  ↓
Aggregate results
```

## What's Actually Tested

✅ **Working and Verified:**
- RPC model sharding with 13B models across 2-3 backends
- Layer distribution visible in coordinator logs
- Systemd RPC service installation and management
- Dashboard monitoring of RPC backends
- GGUF extraction from Ollama storage
- Configuration persistence

⚠️ **Partially Tested:**
- 70B+ models (should work but not extensively tested)
- Hybrid mode (both sharding + task distribution together)
- RPC auto-discovery (implemented but may have edge cases)

❌ **Not Yet Implemented:**
- Automatic model-size routing thresholds
- GPU memory-aware backend selection
- Pipeline parallelism
- Ray integration

## Design Decisions

### Why Cache RPC Health Checks?

RPC servers have backlogs of ~2 connections. When coordinator connects, the backlog fills instantly. Health checks then fail with EAGAIN even though the backend is working perfectly. Solution: trust initial health check, cache status for 5 minutes.

### Why Ephemeral Coordinators?

Each query may need different models. Starting/stopping coordinators per-request allows dynamic model selection without keeping multiple coordinators running. Startup overhead is acceptable for the flexibility gained.

### Why Extract GGUF from Ollama?

Avoids duplicate model storage. Users `ollama pull model` once, both Ollama and llama.cpp can use it. No manual GGUF downloads or path configuration needed.

## Comparison to Alternatives

| Feature | SOLLOL | vLLM/Ray | Petals | Raw llama.cpp |
|---------|--------|----------|--------|---------------|
| Model Sharding | ✅ Layer-level | ✅ Tensor/Pipeline | ✅ Layers | ✅ Layers |
| Task Distribution | ✅ Ollama pool | ❌ | ❌ | ❌ |
| Homelab-Friendly | ✅ Systemd services | ❌ Complex | ❌ P2P | ❌ Manual |
| Ollama Compatible | ✅ GGUF extraction | ❌ | ❌ | ❌ |
| Health Monitoring | ✅ Dashboard | ⚠️ Basic | ❌ | ❌ |
| Setup Complexity | ⭐⭐ Medium | ⭐⭐⭐⭐ High | ⭐⭐⭐ High | ⭐ Low |

## Future Enhancements

Prioritized by user value:

1. **Automatic routing thresholds** - Route <13B to Ollama, ≥13B to RPC automatically
2. **GPU memory tracking** - Select backends based on available VRAM
3. **Persistent coordinators** - Optional mode to keep coordinators running
4. **Better error messages** - User-friendly troubleshooting
5. **Benchmark suite** - Validate performance claims with data

## Contributing

SOLLOL welcomes contributions. Focus areas:
- Testing with 70B+ models
- GPU memory-aware scheduling
- Pipeline parallelism support
- Better documentation of actual performance characteristics
