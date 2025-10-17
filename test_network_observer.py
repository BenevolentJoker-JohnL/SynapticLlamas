#!/usr/bin/env python3
"""
Test NetworkObserver initialization and Redis connectivity.
"""
import sys
sys.path.insert(0, '/home/joker/.local/lib/python3.10/site-packages')

from sollol.network_observer import get_observer, log_ollama_request, log_ollama_response
import time

def test_network_observer():
    print("=" * 60)
    print("Testing NetworkObserver Initialization")
    print("=" * 60)

    # Get the global observer
    observer = get_observer()

    print(f"\n✓ Observer instance created: {observer}")
    print(f"  - Redis client: {observer.redis_client}")

    # Test Redis connection
    redis_working = False
    if observer.redis_client:
        try:
            observer.redis_client.ping()
            print(f"  - ✓ Redis connection: WORKING")
            redis_working = True
        except Exception as e:
            print(f"  - ✗ Redis connection: FAILED - {e}")
    else:
        print(f"  - ✗ Redis client: NOT INITIALIZED")

    # Get current stats
    stats = observer.get_stats()
    print(f"\n📊 Current Stats:")
    print(f"  - Total events: {stats['total_events']}")
    print(f"  - Sampled events: {stats['sampled_events']}")
    print(f"  - Events in memory: {stats['events_in_memory']}")
    print(f"  - Backends tracked: {stats['backends_tracked']}")

    # Test logging an event
    print(f"\n🧪 Testing event logging...")
    log_ollama_request(
        backend="test_node:11434",
        model="llama3.2",
        operation="chat",
        test=True
    )
    time.sleep(0.5)  # Give async thread time to process

    log_ollama_response(
        backend="test_node:11434",
        model="llama3.2",
        latency_ms=123.45,
        test=True
    )
    time.sleep(0.5)

    # Check if events were logged
    stats_after = observer.get_stats()
    print(f"  - Events after test: {stats_after['total_events']} (was {stats['total_events']})")

    if stats_after['total_events'] > stats['total_events']:
        print(f"  - ✓ Events are being logged!")
    else:
        print(f"  - ✗ Events are NOT being logged!")

    # Check recent events
    recent_events = observer.get_recent_events(limit=5)
    print(f"\n📝 Recent events ({len(recent_events)}):")
    for event in recent_events:
        print(f"  - {event['event_type']} | {event['backend']} | {event.get('details', {}).get('model', 'N/A')}")

    print("\n" + "=" * 60)

    return observer

if __name__ == "__main__":
    observer = test_network_observer()
