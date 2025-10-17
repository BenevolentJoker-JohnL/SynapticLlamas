# Monitoring Architecture

## Principle: Apps Don't Poll Themselves

**SynapticLlamas should NOT constantly poll its own APIs.**

Instead:
- **Push events** when they happen (event-driven)
- Let the **dashboard** do any polling (only when someone is watching)

## Architecture

```
┌─────────────────────────────────────┐
│      SynapticLlamas                 │
│                                     │
│  ✅ Push events when they happen    │
│     - Redis pub/sub                 │
│     - Dashboard registration        │
│                                     │
│  ❌ NO constant self-polling        │
│                                     │
└──────────────┬──────────────────────┘
               │
               │ (event push only)
               │
               ▼
┌──────────────────────────────────────┐
│    SOLLOL Unified Dashboard          │
│         (port 8080)                  │
│                                      │
│  ✅ Can poll when user is viewing    │
│  ✅ Displays real-time events        │
│  ✅ Aggregates from multiple apps    │
│                                      │
└──────────────────────────────────────┘
```

## Event-Driven Monitoring (Redis)

### Enable Redis Logging

```bash
SynapticLlamas> redis on
```

This publishes events to Redis pub/sub:
- Coordinator start/stop
- RPC backend connect/disconnect
- Model loading
- Errors
- Raw llama.cpp logs

### Subscribe from Dashboard

The SOLLOL dashboard subscribes to these events and displays them in real-time.

No polling needed!

## What Polling Remains

### SynapticLlamas (Minimal)
- **llama.cpp state check**: Every 60 seconds
  - Only detects coordinator start/stop
  - Not for active monitoring
  - Use Redis pub/sub for real-time logs

- **Ollama monitoring**: DISABLED
  - Use SOLLOL dashboard instead
  - Legacy endpoint kept for compatibility

### SOLLOL Dashboard (Acceptable)
- Can poll when user has dashboard open
- Polls from its end, not from app
- User-driven, not background noise

## Migration Path

### Old Way (Deprecated)
```bash
# Don't use SynapticLlamas' built-in dashboard
SynapticLlamas> dashboard  # ❌ Uses legacy polling
```

### New Way (Recommended)
```bash
# 1. Start SynapticLlamas
python3 main.py --distributed

# 2. Enable Redis logging
SynapticLlamas> redis on

# 3. Use SOLLOL unified dashboard (runs separately)
#    Dashboard polls as needed, SynapticLlamas just pushes events
```

## Benefits

1. **No HTTP spam** from SynapticLlamas
2. **Real-time events** via Redis pub/sub
3. **Scalable** - dashboard can monitor multiple apps
4. **Efficient** - apps don't waste resources polling themselves
5. **Separation of concerns** - apps focus on work, dashboard focuses on monitoring

## Implementation

### Events Published to Redis

```python
# Coordinator started
{
  "timestamp": 1704067200.123,
  "component": "coordinator",
  "event_type": "start",
  "message": "llama.cpp coordinator started",
  "details": {
    "port": 8080,
    "rpc_backends": ["192.168.1.10:50052"],
    "model_path": "/path/to/model.gguf"
  }
}
```

### Dashboard Subscribes

```bash
# Dashboard automatically subscribes to:
redis-cli psubscribe "synapticllamas:llama_cpp:*"
```

### Result
- **SynapticLlamas**: Pushes events, no polling
- **Dashboard**: Receives events, displays them
- **HTTP traffic**: Minimal, only when actions happen

## Environment Variable Configuration

SOLLOL v0.9.52+ supports environment variables for configuring heartbeat and monitoring behavior:

### RPC Coordinator Heartbeat

```bash
# Configure RPC coordinator heartbeat interval (default: 30 seconds)
export SOLLOL_RPC_HEARTBEAT_INTERVAL=30
```

**What it does**: Controls how often the llama.cpp coordinator logs heartbeat events to the network observer.

**When to change**:
- **Lower (10-15s)**: More frequent dashboard updates, better real-time visibility
- **Higher (60-120s)**: Reduce overhead in production environments

### RPC Backend Registry Heartbeat

```bash
# Enable/disable periodic health checks for all RPC backends (default: true)
export SOLLOL_RPC_BACKEND_HEARTBEAT=true

# Configure health check interval for all backends (default: 30 seconds)
export SOLLOL_RPC_BACKEND_HEARTBEAT_INTERVAL=30
```

**What it does**: Periodically checks health of all RPC backends and logs aggregated status to network observer.

**When to change**:
- **Lower (10-15s)**: Faster detection of backend failures
- **Higher (60-120s)**: Reduce network overhead from health checks
- **Disable**: Set to `false` if you don't need periodic health monitoring

### Network Observer Configuration

```bash
# Maximum events to keep in memory (default: 10000)
export SOLLOL_OBSERVER_MAX_EVENTS=10000

# Redis connection URL (default: redis://localhost:6379)
export SOLLOL_REDIS_URL=redis://localhost:6379

# Enable/disable event sampling (default: true)
export SOLLOL_OBSERVER_SAMPLING=true

# Sample rate for info events (default: 0.1 = 10%)
export SOLLOL_OBSERVER_SAMPLE_RATE=0.1
```

**Sample Rate Explained**:
- `1.0` (100%) = Log ALL events (recommended for debugging, may impact performance)
- `0.1` (10%) = Log 10% of info events, all warnings/errors (production default)
- `0.0` (0%) = Log only warnings/errors, drop all info events (minimal overhead)

**When to change**:
- **Development**: Set `SOLLOL_OBSERVER_SAMPLE_RATE=1.0` for full visibility
- **Production**: Keep default `0.1` or lower to reduce overhead
- **High traffic**: Lower sample rate to reduce memory/CPU usage

### Example Configuration

```bash
# ~/.bashrc or ~/.zshrc

# Development environment - full visibility
export SOLLOL_RPC_HEARTBEAT_INTERVAL=10
export SOLLOL_OBSERVER_SAMPLE_RATE=1.0
export SOLLOL_OBSERVER_SAMPLING=true

# Production environment - minimal overhead
export SOLLOL_RPC_HEARTBEAT_INTERVAL=60
export SOLLOL_OBSERVER_SAMPLE_RATE=0.05
export SOLLOL_OBSERVER_SAMPLING=true
```

## RPC Backend Heartbeat Behavior

SOLLOL v0.9.52+ now includes **automatic periodic health checks** for all RPC backends.

**What you'll see**:
1. **Coordinator heartbeat** - `rpc_backend_connect on 127.0.0.1:18080` (every 30s)
   - The llama.cpp coordinator logging its status
   - Includes which RPC backends it's using

2. **Backend registry heartbeat** - `rpc_backend_connect on rpc_registry` (every 30s)
   - Aggregated health status of ALL RPC backends
   - Shows: `10.9.66.154:50052, 10.9.66.48:50052, 10.9.66.45:50052, 10.9.66.90:50052`
   - Includes total_configured and total_active counts

**Why not individual backend heartbeats?**
- RPC backends (10.9.66.154:50052, etc.) are passive RPC servers
- They don't actively report status - they're checked by the registry
- The registry aggregates all backends into a single heartbeat for efficiency
- Individual backend health is included in the aggregated message

## Summary

✅ **DO**: Push events when they happen (Redis pub/sub)
✅ **DO**: Let dashboard poll (it's watching anyway)
✅ **DO**: Configure via environment variables for your use case
❌ **DON'T**: Make apps constantly poll themselves
❌ **DON'T**: Duplicate monitoring in multiple places
