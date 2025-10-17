# Testing RPC Routing Fix - Quick Guide

## What Was Fixed

SOLLOL v0.9.52 fixes the routing issue where SynapticLlamas was creating an unwanted Ollama pool and routing to Ray pools instead of using RPC model sharding.

## Verification Test

### Step 1: Restart SynapticLlamas
```bash
cd /home/joker/SynapticLlamas
python synaptic_llamas.py
```

### Step 2: Check Configuration
Type: `distributed model`

**Expected Output:**
```
✅ MODEL SHARDING MODE
Using 4 RPC backend(s):
  • 10.9.66.154:50052
  • 10.9.66.48:50052
  • 10.9.66.45:50052
  • 10.9.66.90:50052
```

### Step 3: Look for Fix Confirmation in Logs

When SynapticLlamas initializes, you should see:

**✅ CORRECT (v0.9.52 with fix):**
```
📦 SOLLOL v0.9.52 - RayHybridRouter initializing
⏭️  Ollama pool disabled (using RPC backends for inference)
📦 Creating 2 sharded model pools (2 backends per pool)
  Pool 0: 2 backends (port 18080)
  Pool 1: 2 backends (port 18081)
✅ RayHybridRouter initialized: 2 RPC pools, 4 total backends
```

**❌ WRONG (v0.9.51 without fix):**
```
📦 SOLLOL v0.9.51 - RayHybridRouter initializing
✅ Auto-configured Ollama pool (3 nodes)  ← BAD! Should not create Ollama pool
📦 Creating 2 sharded model pools...
```

### Step 4: Test Inference

Type a query: `EXPLAIN STRING THEORY`

**Expected Behavior:**

1. **First query (model loading):**
   - Takes 2-5 minutes as coordinator starts and distributes 70B model across RPC backends
   - Look for log: `Routing llama3.1:70b to RPC sharding`
   - You'll see: `Starting llama-server coordinator... --rpc 10.9.66.154:50052,...`
   - Model layers distribute across 4 RPC backends
   - First response returns after model fully loaded

2. **Subsequent queries:**
   - Fast inference (~1-3 seconds per token)
   - No model reload needed
   - Coordinator already running

**You should NOT see:**
- ❌ `ray.exceptions.GetTimeoutError`
- ❌ `Routing to Ray pool`
- ❌ `Auto-configured Ollama pool`

**You SHOULD see:**
- ✅ `Routing llama3.1:70b to RPC sharding (no Ollama pool available)`
- ✅ `Starting llama-server coordinator`
- ✅ `--rpc 10.9.66.154:50052,10.9.66.48:50052,10.9.66.45:50052,10.9.66.90:50052`

## What to Expect

### Startup Performance
- **Ray initialization**: ~5 seconds
- **Dask initialization**: ~3 seconds
- **RPC backend health checks**: ~1 second
- **Ray pool creation**: ~2 seconds
- **Total startup**: ~10-15 seconds

### First Query Performance
- **GGUF resolution**: <1 second
- **Coordinator startup**: ~10-30 seconds
- **Model layer distribution**: 2-5 minutes for 70B model
- **First token**: After model fully loaded
- **Total first query**: 2-5 minutes

### Subsequent Query Performance
- **Routing decision**: <1ms
- **Coordinator communication**: <10ms
- **Time to first token**: ~1-3 seconds
- **Tokens/second**: 5-15 t/s (depends on network bandwidth and RPC backend hardware)

## Troubleshooting

### Issue: Still seeing "Auto-configured Ollama pool"

**Cause**: Old SOLLOL version still loaded in memory

**Fix**:
```bash
pip show sollol  # Check version
# Should show: Version: 0.9.52

# If not v0.9.52:
pip install --force-reinstall --no-deps ~/SOLLOL

# Then restart SynapticLlamas
```

### Issue: "No Ollama pool and no RPC backends available"

**Cause**: RPC backends not discovered

**Fix**:
```bash
# Verify RPC backends reachable
timeout 1 bash -c "cat < /dev/null > /dev/tcp/10.9.66.154/50052 2>/dev/null" && echo "154 OK"
timeout 1 bash -c "cat < /dev/null > /dev/tcp/10.9.66.48/50052 2>/dev/null" && echo "48 OK"
timeout 1 bash -c "cat < /dev/null > /dev/tcp/10.9.66.45/50052 2>/dev/null" && echo "45 OK"
timeout 1 bash -c "cat < /dev/null > /dev/tcp/10.9.66.90/50052 2>/dev/null" && echo "90 OK"

# Check config
cat ~/.synapticllamas.json | grep -A20 rpc_backends
```

### Issue: Coordinator times out during model loading

**Cause**: 70B model takes >3 minutes to distribute across 4 backends

**Current Behavior**: Timeout after 300s (5 minutes)

**Future Improvement Needed**:
- Increase Ray timeout to 600s (10 minutes) for very large models
- Add progress reporting during model loading
- Implement coordinator pre-warming at startup

**Workaround**:
- Wait for coordinator startup to complete in background
- Monitor with: `ps aux | grep llama-server`
- Once running, subsequent queries will work

## Success Indicators

✅ **Routing Fix Working:**
- Logs show "Ollama pool disabled (using RPC backends for inference)"
- Queries route to RPC sharding
- No Ray timeout errors

✅ **Model Sharding Working:**
- Coordinator starts with `--rpc` flag listing all 4 backends
- Model loads across multiple nodes
- Inference completes successfully

✅ **CPU+GPU Parallelization:**
- llama.cpp automatically detects CPU/GPU on each RPC backend
- Layers distribute based on device capabilities
- Check llama-server logs for "using device RPC0 (CUDA)" or "using device RPC3 (CPU)"

## Test Commands

```bash
# 1. Check SOLLOL version
pip show sollol | grep Version

# 2. Verify RPC backend connectivity
for host in 10.9.66.154 10.9.66.48 10.9.66.45 10.9.66.90; do
  echo "=== Testing $host ==="
  timeout 1 bash -c "cat < /dev/null > /dev/tcp/$host/50052 2>/dev/null" && echo "✅ REACHABLE" || echo "❌ NOT REACHABLE"
done

# 3. Check coordinator status (after first query)
ps aux | grep llama-server | grep -v grep

# 4. Check coordinator health (after first query)
curl -s http://127.0.0.1:18080/health || echo "Coordinator not running"

# 5. Monitor coordinator logs (if needed)
# Look in SynapticLlamas output for llama-server logs
```

## Next Steps After Successful Test

Once verified working:

1. **Performance Tuning**:
   - Adjust `backends_per_pool` for optimal load distribution
   - Tune `--ctx-size` for your workload
   - Monitor GPU memory usage across backends

2. **Production Deployment**:
   - Consider coordinator pre-warming at startup
   - Implement health monitoring for RPC backends
   - Set up alerting for coordinator failures

3. **Expand Configuration**:
   - Add more RPC backends for larger models
   - Test with different model sizes
   - Implement model-specific coordinator configs
