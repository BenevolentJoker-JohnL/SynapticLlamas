#!/usr/bin/env python3
"""
Test NetworkObserver with concurrent Redis monitoring.
"""
import sys
sys.path.insert(0, '/home/joker/.local/lib/python3.10/site-packages')

import threading
import time
import redis
import json
from sollol.network_observer import log_ollama_request, log_ollama_response, get_observer

def monitor_redis(duration=5):
    """Monitor Redis channels for activity."""
    r = redis.from_url("redis://localhost:6379", decode_responses=True)
    pubsub = r.pubsub()
    pubsub.subscribe("sollol:dashboard:ollama:activity")

    print("📡 Monitoring Redis channel 'sollol:dashboard:ollama:activity'...")

    start_time = time.time()
    message_count = 0

    while time.time() - start_time < duration:
        message = pubsub.get_message(timeout=0.1)
        if message and message['type'] == 'message':
            message_count += 1
            data = json.loads(message['data'])
            print(f"   📨 Message #{message_count}: {data['event_type']} | {data.get('details', {}).get('model', 'N/A')}")

    pubsub.close()
    return message_count

def main():
    print("=" * 60)
    print("Testing NetworkObserver with Live Monitoring")
    print("=" * 60)

    # Get observer
    observer = get_observer()
    print(f"\n✓ Observer initialized")
    print(f"  - Redis client: {'YES' if observer.redis_client else 'NO'}")

    # Start monitoring thread
    monitor_thread = threading.Thread(target=lambda: monitor_redis(5))
    monitor_thread.start()

    time.sleep(0.5)  # Let monitor start

    # Generate test events
    print("\n🧪 Generating test events...")
    for i in range(10):
        print(f"   - Logging request #{i+1}")
        log_ollama_request(
            backend=f"test_node_{i % 3}:11434",
            model="llama3.2",
            operation="chat",
            test_id=i
        )
        time.sleep(0.2)

        log_ollama_response(
            backend=f"test_node_{i % 3}:11434",
            model="llama3.2",
            latency_ms=100 + i * 10,
            test_id=i
        )
        time.sleep(0.2)

    # Wait for monitor to finish
    monitor_thread.join()

    # Check stats
    stats = observer.get_stats()
    print(f"\n📊 Final Stats:")
    print(f"  - Total events: {stats['total_events']}")
    print(f"  - Sampled events: {stats['sampled_events']}")
    print(f"  - Dropped events: {stats['dropped_events']}")
    print(f"  - Sampling rate: {stats['sample_rate']:.0%}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
