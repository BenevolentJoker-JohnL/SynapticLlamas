# Redis Logging for llama.cpp Live Logs

SynapticLlamas now supports real-time Redis publishing of llama.cpp coordinator and RPC backend logs, enabling external monitoring systems to consume logs via Redis pub/sub.

## Features

- **Real-time log streaming** to Redis pub/sub channels
- **Structured log events** with timestamps, component types, and metadata
- **Raw log capture** from llama.cpp coordinator stdout
- **Multiple channels** for different log types
- **Automatic connection management** with retry logic

## Redis Channels

All logs are published to dedicated Redis channels:

| Channel | Description |
|---------|-------------|
| `synapticllamas:llama_cpp:logs` | All llama.cpp related logs (unified feed) |
| `synapticllamas:llama_cpp:coordinator` | Coordinator-specific events (start/stop/errors) |
| `synapticllamas:llama_cpp:rpc_backends` | RPC backend connection/disconnection events |
| `synapticllamas:llama_cpp:metrics` | Performance metrics and statistics |
| `synapticllamas:llama_cpp:raw` | Raw stdout logs from llama.cpp |

## Configuration

### Environment Variables

You can configure Redis connection via environment variables:

```bash
export REDIS_HOST=localhost
export REDIS_PORT=6379
export REDIS_DB=0
export REDIS_PASSWORD=your_password  # Optional
```

### Configuration File

Redis settings are stored in `~/.synapticllamas.json`:

```json
{
  "redis_logging_enabled": false,
  "redis_host": "localhost",
  "redis_port": 6379,
  "redis_db": 0,
  "redis_password": null
}
```

### Interactive CLI

Enable/disable Redis logging during runtime:

```bash
SynapticLlamas> redis on
✅ Redis log publishing ENABLED
   Publishing to localhost:6379
   Channels:
     • synapticllamas:llama_cpp:logs (all logs)
     • synapticllamas:llama_cpp:coordinator (coordinator events)
     • synapticllamas:llama_cpp:rpc_backends (RPC backend events)
     • synapticllamas:llama_cpp:raw (raw stdout logs)

SynapticLlamas> redis off
✅ Redis log publishing DISABLED
```

## Usage

### 1. Start Redis Server

```bash
# Using Docker
docker run -d --name redis -p 6379:6379 redis:latest

# Or using local Redis
redis-server
```

### 2. Enable Redis Logging in SynapticLlamas

```bash
# Start SynapticLlamas in distributed mode
python3 main.py --distributed

# Enable Redis logging
SynapticLlamas> redis on
```

### 3. Subscribe to Logs from Another Terminal

#### Subscribe to All Logs

```bash
redis-cli subscribe synapticllamas:llama_cpp:logs
```

#### Subscribe to Coordinator Events Only

```bash
redis-cli subscribe synapticllamas:llama_cpp:coordinator
```

#### Subscribe to Multiple Channels

```bash
redis-cli psubscribe "synapticllamas:llama_cpp:*"
```

### 4. Use Distributed Inference (triggers log publishing)

```bash
# Enable model sharding
SynapticLlamas> distributed model

# Run a query with a large model
SynapticLlamas> Explain quantum computing using llama3.1:70b
```

## Log Event Format

### Structured Events

Structured log events are published as JSON:

```json
{
  "timestamp": 1704067200.123,
  "component": "coordinator",
  "level": "info",
  "message": "llama.cpp coordinator started on port 8080",
  "event_type": "start",
  "details": {
    "model_path": "/path/to/model.gguf",
    "port": 8080,
    "rpc_backends": ["192.168.1.10:50052", "192.168.1.11:50052"],
    "backend_count": 2,
    "host": "127.0.0.1",
    "n_gpu_layers": 99,
    "ctx_size": 2048
  }
}
```

### Raw Logs

Raw logs from llama.cpp stdout:

```json
{
  "timestamp": 1704067200.456,
  "source": "coordinator",
  "line": "llama_model_loader: loaded meta data with 20 key-value pairs"
}
```

## Event Types

| Event Type | Description | Component |
|------------|-------------|-----------|
| `start` | Coordinator started | coordinator |
| `stop` | Coordinator stopped | coordinator |
| `model_load` | Model loaded | model |
| `connect` | RPC backend connected | rpc_backend |
| `disconnect` | RPC backend disconnected | rpc_backend |
| `error` | Error occurred | any |
| `status` | Status update | any |

## Example: Monitoring with Python

```python
import redis
import json

# Connect to Redis
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# Subscribe to all llama.cpp logs
pubsub = r.pubsub()
pubsub.subscribe('synapticllamas:llama_cpp:logs')

print("Listening for llama.cpp logs...")

for message in pubsub.listen():
    if message['type'] == 'message':
        try:
            log_event = json.loads(message['data'])
            timestamp = log_event['timestamp']
            component = log_event['component']
            level = log_event['level']
            msg = log_event['message']

            print(f"[{timestamp}] [{component}] [{level}] {msg}")

            # Access additional details
            if 'details' in log_event:
                print(f"  Details: {log_event['details']}")
        except json.JSONDecodeError:
            print(f"Raw message: {message['data']}")
```

## Example: Monitoring with redis-cli

```bash
# Subscribe and format output
redis-cli --csv psubscribe "synapticllamas:llama_cpp:*" | while IFS=',' read -r type pattern channel message; do
    echo "Channel: $channel"
    echo "Message: $message" | jq '.'
    echo "---"
done
```

## Example: Alerting on Errors

```python
import redis
import json
from datetime import datetime

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
pubsub = r.pubsub()
pubsub.subscribe('synapticllamas:llama_cpp:logs')

for message in pubsub.listen():
    if message['type'] == 'message':
        try:
            log_event = json.loads(message['data'])

            # Alert on errors
            if log_event['level'] == 'error':
                print(f"🚨 ERROR DETECTED at {datetime.now()}")
                print(f"   Component: {log_event['component']}")
                print(f"   Message: {log_event['message']}")

                # Send alert (email, Slack, PagerDuty, etc.)
                # send_alert(log_event)

        except json.JSONDecodeError:
            pass
```

## Integration with Monitoring Systems

### Prometheus

Use [redis_exporter](https://github.com/oliver006/redis_exporter) to export Redis metrics to Prometheus.

### Grafana

Create a datasource using Redis and visualize:
- Coordinator uptime
- RPC backend health
- Error rates
- Log volume

### ELK Stack (Elasticsearch, Logstash, Kibana)

Configure Logstash to consume from Redis pub/sub:

```ruby
input {
  redis {
    host => "localhost"
    port => 6379
    data_type => "pattern_channel"
    pattern => "synapticllamas:llama_cpp:*"
    codec => json
  }
}

output {
  elasticsearch {
    hosts => ["localhost:9200"]
    index => "synapticllamas-logs-%{+YYYY.MM.dd}"
  }
}
```

## Performance Considerations

- Redis publishing is **non-blocking** - failed publishes won't affect llama.cpp operations
- Connection retries are handled automatically (max 3 retries with 1s delay)
- All logs are published **asynchronously** via Redis pub/sub
- Raw logs are throttled to important events only (model loading, RPC distribution)

## Troubleshooting

### Redis Connection Failed

```bash
# Check Redis is running
redis-cli ping
# Should return: PONG

# Check Redis connection
redis-cli -h localhost -p 6379
```

### No Logs Appearing

1. Ensure Redis logging is enabled:
   ```bash
   SynapticLlamas> redis on
   ```

2. Check Redis publisher status:
   ```python
   from redis_log_publisher import get_global_publisher
   pub = get_global_publisher()
   if pub:
       print(pub.get_stats())
   ```

3. Verify Redis subscription:
   ```bash
   redis-cli pubsub channels "synapticllamas:*"
   ```

### Firewall Issues

If Redis is on a remote server:

```bash
# Allow Redis port
sudo ufw allow 6379/tcp

# Bind Redis to all interfaces (redis.conf)
bind 0.0.0.0
```

## Security

- **Never expose Redis to the public internet** without authentication
- Use `redis_password` in config for authenticated connections
- Consider using Redis over TLS for production environments
- Use Redis ACLs to restrict pub/sub access

## Architecture

```
┌─────────────────────────────────────┐
│   SynapticLlamas Main Process       │
│                                     │
│   ┌─────────────────────────────┐  │
│   │  llama.cpp Coordinator      │  │
│   │  - Logs to stdout           │  │
│   │  - Structured events        │  │
│   └──────────┬──────────────────┘  │
│              │                      │
│   ┌──────────▼──────────────────┐  │
│   │  Redis Log Publisher        │  │
│   │  - Formats events           │  │
│   │  - Publishes to channels    │  │
│   └──────────┬──────────────────┘  │
└──────────────┼──────────────────────┘
               │
               ▼
     ┌─────────────────┐
     │  Redis Server   │
     │  (pub/sub)      │
     └────┬───┬───┬────┘
          │   │   │
   ┌──────▼┐ ┌▼───▼─────┐ ┌────▼─────┐
   │Monitor│ │Dashboard │ │Analytics │
   │Script │ │ (Grafana)│ │  (ELK)   │
   └───────┘ └──────────┘ └──────────┘
```

## API Reference

See [`redis_log_publisher.py`](redis_log_publisher.py) for full API documentation.

### Key Classes

- `RedisLogPublisher` - Main publisher class
- `LlamaCppLogEvent` - Structured log event
- `ComponentType` - Enum of component types (COORDINATOR, RPC_BACKEND, SYSTEM, MODEL)
- `LogLevel` - Enum of log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)

### Global Functions

- `initialize_global_publisher()` - Initialize global publisher instance
- `get_global_publisher()` - Get global publisher instance
- `shutdown_global_publisher()` - Shutdown global publisher

## License

Same as SynapticLlamas (see main LICENSE file).
