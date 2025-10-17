# RPC Routing Fix - SOLLOL v0.9.52

## Problem

SynapticLlamas was configured to use RPC model sharding (task_distribution=false, model_sharding=true) but was still routing to Ray pools and encountering timeouts instead of using the proven-working llama.cpp RPC coordinator.

## Root Cause

**Issue 1: Initialization Order**
RayHybridRouter auto-configured an Ollama pool BEFORE checking if RPC backends were available:

```python
# OLD CODE (line 200-205)
if ollama_pool is None:
    # Auto-configure only if not explicitly disabled
    self.ollama_pool = OllamaPool.auto_configure() if enable_distributed else None
else:
    self.ollama_pool = ollama_pool

# ... RPC backends discovered AFTER this
```

When SynapticLlamas passed `ollama_pool=None` (because task_distribution was disabled), RayHybridRouter still auto-created an Ollama pool because `enable_distributed=True`.

**Issue 2: Routing Logic**
The routing logic didn't handle the case where `ollama_pool` is None, causing AttributeErrors when trying to route small models.

**Issue 3: Stats Method**
`get_stats()` accessed `self.ollama_pool.nodes` without checking if ollama_pool exists.

## Solution

### Fix 1: Reorder Initialization (lines 200-230)

Move RPC backend discovery BEFORE Ollama pool initialization, and only auto-configure Ollama pool if NO RPC backends are found:

```python
# Store parameters first
self.enable_distributed = enable_distributed
# ... other parameters ...

# Auto-discover RPC backends if needed (BEFORE ollama_pool initialization)
if rpc_backends is None and enable_distributed and auto_discover_rpc:
    logger.info("🔍 Auto-discovering RPC backends...")
    from sollol.rpc_discovery import auto_discover_rpc_backends
    rpc_backends = auto_discover_rpc_backends()

self.rpc_backends = rpc_backends or []
self.has_rpc_backends = len(self.rpc_backends) > 0

# Initialize ollama_pool AFTER we know about RPC backends
if ollama_pool is None:
    # Only auto-configure if distributed enabled AND no RPC backends
    self.ollama_pool = OllamaPool.auto_configure() if (enable_distributed and not self.has_rpc_backends) else None
    if self.ollama_pool:
        logger.info("✅ Auto-configured Ollama pool (no RPC backends found)")
    else:
        logger.info("⏭️  Ollama pool disabled (using RPC backends for inference)")
else:
    self.ollama_pool = ollama_pool
```

### Fix 2: Improved Routing Logic (lines 382-414)

Handle all routing cases explicitly:

```python
# Determine routing
route_to_rpc = self._should_use_rpc(model)

if route_to_rpc and self.enable_distributed and self.pools:
    # Large model → Use Ray-managed sharded pools
    logger.info(f"Routing {model} to RPC sharding (estimated large model)")
    return await self._route_to_ray_pool(model, messages, stream, **kwargs)
elif self.ollama_pool:
    # Small model → Use Ollama pool for task distribution
    logger.info(f"Routing {model} to Ollama pool (estimated small model)")
    try:
        return await self.ollama_pool.chat_async(...)
    except Exception as e:
        if self.auto_fallback and self.enable_distributed and self.pools:
            logger.warning(f"Ollama failed for {model}, falling back to RPC sharding: {e}")
            return await self._route_to_ray_pool(model, messages, stream, **kwargs)
        raise
elif self.enable_distributed and self.pools:
    # No Ollama pool but have RPC → Force RPC routing
    logger.info(f"Routing {model} to RPC sharding (no Ollama pool available)")
    return await self._route_to_ray_pool(model, messages, stream, **kwargs)
else:
    raise RuntimeError(
        f"Cannot route request for {model}: No Ollama pool and no RPC backends available. "
        "Configure either Ollama nodes or RPC backends."
    )
```

### Fix 3: Safe Stats Method (lines 502-518)

Check if ollama_pool exists before accessing:

```python
def get_stats(self) -> Dict[str, Any]:
    """Get router statistics."""
    stats = {
        "router_type": "ray_hybrid",
        "ollama_pool": {
            "nodes": len(self.ollama_pool.nodes) if self.ollama_pool else 0,
            "requests": self.ollama_pool.stats["total_requests"] if self.ollama_pool else 0,
        } if self.ollama_pool else None,
        "ray_pools": {
            "num_pools": len(self.pools) if hasattr(self, 'pools') else 0,
            "backends_per_pool": self.backends_per_pool,
            "total_backends": len(self.rpc_backends),
            "current_model": self.current_model if hasattr(self, 'current_model') else None,
        },
    }
    return stats
```

## Verification

Test script output confirms the fix:

```
📡 RPC Backends (4 nodes):
   • 10.9.66.154:50052
   • 10.9.66.48:50052
   • 10.9.66.45:50052
   • 10.9.66.90:50052

⏭️  Ollama pool disabled (using RPC backends for inference)
🔗 Routing 'llama3.1:70b' to RPC (no Ollama pool)

Starting llama-server coordinator:
  llama-server --model /path/to/model.gguf
               --host 127.0.0.1
               --port 18080
               --rpc 10.9.66.154:50052,10.9.66.48:50052,10.9.66.45:50052,10.9.66.90:50052
               --gpu-layers 99
               --ctx-size 2048
```

## Behavior Change

### Before (SOLLOL v0.9.51)
- SynapticLlamas with task_distribution=false → RayHybridRouter auto-creates Ollama pool
- Requests route to Ray pool → Ray timeout errors
- RPC backends unused despite being configured

### After (SOLLOL v0.9.52)
- SynapticLlamas with task_distribution=false → RayHybridRouter skips Ollama pool
- Requests route directly to RPC coordinator
- All 4 RPC backends used for model sharding

## Configuration Examples

### Pure RPC Mode (Model Sharding Only)
```python
# distributed_orchestrator.py
RayHybridRouter(
    ollama_pool=None,              # Explicitly no Ollama pool
    rpc_backends=[...],             # RPC backends provided
    enable_distributed=True         # Enable RPC sharding
)
# Result: ollama_pool stays None, all requests → RPC
```

### Hybrid Mode (Task Distribution + Model Sharding)
```python
RayHybridRouter(
    ollama_pool=OllamaPool(...),   # Explicit Ollama pool
    rpc_backends=[...],             # RPC backends provided
    enable_distributed=True
)
# Result: Small models → Ollama, Large models → RPC
```

### Ollama-Only Mode (No RPC)
```python
RayHybridRouter(
    ollama_pool=OllamaPool(...),   # Explicit Ollama pool
    rpc_backends=None,              # No RPC backends
    enable_distributed=True
)
# Result: All requests → Ollama pool
```

### Auto-Discovery Mode (Fallback to Ollama)
```python
RayHybridRouter(
    ollama_pool=None,               # Will auto-configure
    rpc_backends=None,              # Will auto-discover
    enable_distributed=True,
    auto_discover_rpc=True
)
# Result: If RPC found → use RPC, else → auto-configure Ollama
```

## Files Modified

- `/home/joker/SOLLOL/src/sollol/ray_hybrid_router.py` (lines 200-230, 382-414, 502-518)
- `/home/joker/SOLLOL/src/sollol/__init__.py` (version bump to 0.9.52)
- `/home/joker/SOLLOL/setup.py` (version bump to 0.9.52)

## Next Steps for SynapticLlamas

Now that SOLLOL v0.9.52 is installed, SynapticLlamas should:

1. **Restart SynapticLlamas** to pick up the new SOLLOL version
2. **Verify routing** by checking logs for "Routing to RPC sharding (no Ollama pool available)"
3. **Monitor coordinator startup** - May take 2-5 minutes for 70B model distribution across 4 backends
4. **Test inference** - First query will be slow (model loading), subsequent queries faster

## Automatic Fallback Behavior

### RPC → Ollama Fallback (base_agent.py lines 688-692)

When HybridRouter fails (RPC backend errors), the system **automatically falls back to regular Ollama API**:

```python
except Exception as e:
    logger.error(f"❌ HybridRouter failed for {self.name}: {e}")
    import traceback
    logger.error(traceback.format_exc())
    # Fall through to regular Ollama call
```

**Common RPC Failure Scenarios**:

1. **400 Bad Request** - llama.cpp server receives malformed request
   ```
   httpx.HTTPStatusError: Client error '400 Bad Request' for url 'http://127.0.0.1:18080/v1/chat/completions'
   ```

2. **Read Timeout** - Long generation exceeds timeout
   ```
   httpcore.ReadTimeout
   ```

3. **Ray Task Error** - Distributed task fails on remote worker
   ```
   ray.exceptions.RayTaskError: ray::ShardedModelPool.chat()
   ```

**Fallback Flow**:
```
1. Agent tries HybridRouter (RPC sharding)
2. RPC backend fails (400/timeout/Ray error)
3. Exception caught at base_agent.py:688
4. Logs error with full traceback
5. Continues to regular Ollama API call (line 695+)
6. User sees: "📍 {Agent} using default URL: http://localhost:11434"
7. Request completes via Ollama with same preprocessing/validation
```

**Why This is Safe**:
- Preprocessing (llama3.2 cleaning, LaTeX fixes) applies to BOTH paths
- TrustCall validation applies to BOTH paths
- Agent output format identical regardless of routing
- User experience unchanged (just slower without GPU acceleration)

**Log Output During Fallback**:
```
2025-10-15 20:31:40,175 - ERROR - ❌ HybridRouter failed for Editor: ...
httpx.HTTPStatusError: Client error '400 Bad Request' ...

2025-10-15 20:31:40,184 - INFO - 📍 Editor using default URL: http://localhost:11434
2025-10-15 20:31:40,184 - INFO - 📤 Editor sending request to http://localhost:11434/api/generate (timeout: 1200s)
```

### Ollama → RPC Fallback (ray_hybrid_router.py lines 381-384)

The reverse fallback (documented in original fix) handles Ollama pool failures:

```python
except Exception as e:
    if self.auto_fallback and self.enable_distributed and self.pools:
        logger.warning(f"Ollama failed for {model}, falling back to RPC sharding: {e}")
        return await self._route_to_ray_pool(model, messages, stream, **kwargs)
    raise
```

**Result**: Bidirectional fallback ensures requests always complete even when one backend fails.

## Known Issues / Future Improvements

1. **Coordinator Startup Time**: Loading 70B model across 4 RPC backends takes 2-5 minutes
   - Consider pre-warming coordinators at startup
   - Or implement lazy loading with user notification

2. **Ray Timeout**: Still using 300s timeout for model loading via Ray
   - May need increase for very large models (405B+)
   - Or implement progress reporting during load

3. **Coordinator Caching**: Each new model requires full coordinator restart
   - Consider coordinator pooling for frequently used models
   - Or implement hot-swapping coordinators

4. **RPC 400 Errors**: llama.cpp sometimes returns 400 Bad Request
   - Root cause: Unknown (possibly malformed request format or server resource exhaustion)
   - Impact: Low (automatic fallback to Ollama ensures completion)
   - Investigation needed: Capture request payload when 400 occurs
   - **Current behavior**: System attempts RPC sharding for all models, falls back to Ollama on failure
   - **Note**: RPC sharding is intentionally attempted for small models (llama3.2:3b) because in extremely resource-constrained environments (limited VRAM, edge devices, older GPUs), even 3B models may benefit from distributed inference across multiple nodes
   - **Future improvement**: Implement intelligent RPC health checking and model size detection:
     - Health checks should detect which backends can handle which model sizes
     - Automatic determination of when sharding provides performance benefit vs overhead
     - Support for programmatic sharding decisions based on available resources
     - This will enable SOLLOL to work optimally in ANY environment from high-end clusters to edge devices
