#!/usr/bin/env python3
"""
Check Redis channels for Ollama activity.
"""
import redis
import json
import time

def check_redis_channels():
    print("=" * 60)
    print("Checking Redis Channels for Activity")
    print("=" * 60)

    # Connect to Redis
    r = redis.from_url("redis://localhost:6379", decode_responses=True)

    # Check if Redis is working
    try:
        r.ping()
        print("\n✓ Redis connection: WORKING\n")
    except Exception as e:
        print(f"\n✗ Redis connection: FAILED - {e}\n")
        return

    # Channels to check
    channels = [
        "sollol:dashboard:ollama:activity",
        "sollol:dashboard:rpc:activity",
        "sollol:routing_events",
    ]

    print("📡 Monitoring channels (press Ctrl+C to stop)...")
    print("   Waiting for activity on:")
    for channel in channels:
        print(f"   - {channel}")
    print()

    # Subscribe to channels
    pubsub = r.pubsub()
    for channel in channels:
        pubsub.subscribe(channel)

    print("✓ Subscribed to channels, waiting for messages...\n")

    # Listen for messages (timeout after 5 seconds)
    start_time = time.time()
    timeout = 5
    message_count = 0

    while time.time() - start_time < timeout:
        message = pubsub.get_message(timeout=0.1)
        if message and message['type'] == 'message':
            message_count += 1
            channel = message['channel']
            data = message['data']

            print(f"📨 Message #{message_count} on {channel}:")
            try:
                data_dict = json.loads(data)
                print(f"   {json.dumps(data_dict, indent=2)}")
            except:
                print(f"   {data}")
            print()

    if message_count == 0:
        print("⚠️  No messages received in 5 seconds")
        print("\n💡 This means:")
        print("   1. No Ollama requests are being made, OR")
        print("   2. NetworkObserver is not publishing to Redis, OR")
        print("   3. Events are being sampled out (10% sampling rate)")
    else:
        print(f"\n✓ Received {message_count} messages")

    pubsub.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    try:
        check_redis_channels()
    except KeyboardInterrupt:
        print("\n\nStopped by user")
