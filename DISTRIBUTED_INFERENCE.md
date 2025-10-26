# Distributed Inference with SOLLOL

> **⚠️ EXPERIMENTAL FEATURE**
>
> **Status**: Experimental - Research & Development
>
> Model sharding via llama.cpp RPC is currently in experimental stage. While the implementation is functional for testing and validation, it requires additional development, testing, and performance optimization before being recommended for production use.
>
> **Current State**:
> - ✅ Functional for 13B models across 2-3 nodes (verified)
> - ⚠️ Requires further testing for larger models (70B+)
> - ⚠️ Performance characteristics still being evaluated
> - ⚠️ Network overhead and latency need optimization
>
> **Use For**: Testing, research, development, and validation purposes
> **Not Recommended For**: Production workloads without extensive testing

**Layer-level model sharding for local LLM clusters.**

SOLLOL combines Ollama's model management with llama.cpp's RPC protocol to enable running larger models across multiple consumer machines.

---

## What This Actually Does

**Model sharding:** Splits a single model's layers across multiple RPC backend nodes, allowing inference on models that don't fit in a single machine's memory.

**Verified working:**
- ✅ 13B models across 2-3 nodes
- ✅ Automatic layer distribution by llama-server
- ✅ GGUF extraction from Ollama blob storage
- ✅ Real-time log streaming showing distribution

**Should work (not extensively tested):**
- ⚠️ 70B models across 4+ nodes
- ⚠️ Larger models (405B) with sufficient nodes

**Limitations:**
- Startup time: 2-5 minutes for 13B, potentially longer for 70B+
- Requires GGUF file in Ollama storage
- Manual RPC server setup on each node
- Slower than single-node inference due to network communication

---

## The Problem SOLLOL Solves

**Ollama doesn't support splitting a model across machines.**

If your model doesn't fit on one GPU, Ollama can't help. Options were:
- Buy bigger GPU (expensive)
- Use cloud (privacy/cost concerns)
- Manual llama.cpp setup (complex)

**SOLLOL bridges Ollama and llama.cpp:**
- Pull model once with `ollama pull codellama:13b`
- SOLLOL extracts GGUF automatically
- Distributes it across your existing hardware

---

## How It Works

```
User Query
  ↓
SOLLOL extracts GGUF from Ollama storage
  ↓
Starts llama-server with --rpc backend1,backend2,backend3
  ↓
llama-server distributes layers:
  - Backend 1: Layers 0-13
  - Backend 2: Layers 14-27
  - Backend 3: Layers 28-40
  ↓
Inference across distributed backends
  ↓
Coordinator stops, backends remain ready
```

### Key Technologies

- **Ollama**: Model management and GGUF storage
- **llama.cpp RPC**: Layer distribution protocol
- **llama-server**: Coordinator process
- **SOLLOL**: Orchestration and monitoring

---

## Setup

### 1. Install RPC Servers (Each Node)

```bash
# On each worker node, install systemd service
cd SynapticLlamas/SOLLOL
./scripts/install-rpc-service.sh

# Verify running
systemctl --user status sollol-rpc-server
```

### 2. Configure SynapticLlamas

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

### 3. Pull Model with Ollama

```bash
# Pull model once - SOLLOL will extract GGUF
ollama pull codellama:13b
```

### 4. Run SynapticLlamas

```bash
python3 main.py
```

Now queries automatically use distributed sharding:

```
SynapticLlamas> explain quantum computing

🚀 Command: llama-server --model codellama:13b --rpc 10.9.66.154:50052,10.9.66.157:50052,10.9.66.45:50052
   ⏳ Loading model across RPC backends...
   📊 load_tensors: RPC0[10.9.66.154:50052] model buffer size = 2.3 GiB
   📊 load_tensors: RPC1[10.9.66.157:50052] model buffer size = 2.3 GiB
   📊 load_tensors: RPC2[10.9.66.45:50052] model buffer size = 2.3 GiB
   ✅ Model loaded and ready
```

---

## Performance Characteristics

### Startup Time

**Model loading takes significantly longer than single-node:**

| Model Size | Single Node | 2 Backends | 3 Backends |
|-----------|-------------|------------|------------|
| 13B | ~20s | ~40s | ~40s |
| 70B | N/A (doesn't fit) | Estimated 5-10min | Estimated 5-10min |

**Why?** Each backend loads its layer slice sequentially, plus network coordination overhead.

### Inference Speed

**Distributed inference is slower than local due to network latency:**

| Setup | Tokens/sec (13B) |
|-------|------------------|
| Single RTX 3090 | ~20-30 |
| 2x RPC backends (1Gbps) | ~5-10 |
| 3x RPC backends (1Gbps) | ~5-10 |

**When it's worth it:** When model doesn't fit on single machine at all. Slower inference is better than no inference.

---

## Troubleshooting

### RPC Backend Shows "Offline" During Inference

**This is normal!** RPC servers have tiny connection backlogs (~2). When coordinator connects, queue fills instantly. Health checks fail even though backend is working.

**Solution:** Ignore "offline" status during active inference. It means backend is busy working.

### Model Loading Takes Forever

**Expected:** 2-5 minutes for 13B, potentially 5-10 minutes for 70B+.

**Check:**
1. All RPC servers running: `systemctl --user status sollol-rpc-server`
2. Network connectivity: `nc -zv <host> 50052`
3. Logs for errors: `journalctl --user -u sollol-rpc-server -f`

### "GGUF not found" Error

**Cause:** Model not in Ollama storage.

**Solution:**
```bash
ollama pull <model>  # Downloads and stores GGUF
```

SOLLOL looks in: `/usr/share/ollama/.ollama/models/blobs/`

### Poor Performance

**Check:**
1. Network speed (1Gbps minimum recommended)
2. Backend machines not overloaded
3. Consider single-node if model actually fits

---

## Comparison: When to Use What

### Use SOLLOL RPC Sharding When:
- ✅ Model doesn't fit on single GPU
- ✅ You have 2+ machines available
- ✅ Network is fast (1Gbps+)
- ✅ You can accept slower inference for access to larger models

### Use Standard Ollama When:
- ✅ Model fits on single GPU
- ✅ Speed is critical
- ✅ Simple setup preferred

### Use Task Distribution (Ollama Pool) When:
- ✅ Running multiple independent agent tasks in parallel
- ✅ Each task is separate query
- ✅ Want to max out cluster utilization

---

## Configuration Modes

### Pure Model Sharding

```json
{
  "model_sharding_enabled": true,
  "task_distribution_enabled": false
}
```

All queries → RPC sharding

### Pure Task Distribution

```json
{
  "model_sharding_enabled": false,
  "task_distribution_enabled": true
}
```

All queries → Ollama pool load balancing

### Hybrid (Both)

```json
{
  "model_sharding_enabled": true,
  "task_distribution_enabled": true
}
```

HybridRouter decides per-request (experimental)

---

## Technical Details

### Layer Distribution

llama-server automatically distributes layers across backends based on available memory. SOLLOL doesn't control the split - it's handled by llama.cpp internally.

**Example 13B model (40 layers) on 3 backends:**
- Backend 1: ~13 layers
- Backend 2: ~13 layers
- Backend 3: ~14 layers

### Network Requirements

**Minimum:** 1Gbps Ethernet
**Recommended:** 10Gbps for 70B+ models

RPC protocol sends activations between layers. More layers = more network traffic.

### GGUF Extraction

SOLLOL extracts GGUF from Ollama's blob storage:
1. Query Ollama API for model manifest
2. Find blob hash for model layers
3. Read GGUF from `/usr/share/ollama/.ollama/models/blobs/sha256-<hash>`

No duplication. No manual downloads.

---

## Future Improvements

Prioritized list:

1. **Automatic model-size routing** - Route <13B to Ollama, ≥13B to RPC
2. **Persistent coordinators** - Keep coordinator running for repeated queries
3. **Memory-aware backend selection** - Use backends with most free VRAM
4. **Performance benchmarks** - Document actual speed vs model size
5. **Better error messages** - User-friendly troubleshooting guidance

---

## Contributing

Help wanted:
- Testing with 70B+ models on real hardware
- Performance benchmarking across different network speeds
- Documentation improvements based on actual usage
- Bug reports with specific error messages and logs

---

## Acknowledgments

- **llama.cpp**: RPC protocol and coordinator
- **Ollama**: Model management and GGUF storage
- **Community**: Testing and feedback
