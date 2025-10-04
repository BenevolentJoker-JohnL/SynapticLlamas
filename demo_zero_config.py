#!/usr/bin/env python3
"""
Demo: Zero-Config SOLLOL - "Just Works"

Shows how SOLLOL auto-discovers Ollama nodes and works immediately.
No configuration files. No setup. Just import and use.
"""

from sollol import Ollama
import time


def main():
    print("=" * 60)
    print("SOLLOL Zero-Config Demo")
    print("=" * 60)
    print()

    # Step 1: Create client (auto-discovers nodes)
    print("Step 1: Creating Ollama client (auto-discovery)...")
    start = time.time()
    client = Ollama()
    discovery_time = time.time() - start
    print(f"✓ Client ready in {discovery_time:.3f}s")
    print()

    # Step 2: Show discovered nodes
    stats = client.get_stats()
    print(f"Step 2: Auto-discovered {stats['nodes_configured']} nodes:")
    for node in stats['nodes']:
        print(f"  • {node}")
    print()

    # Step 3: Chat completion (simple string)
    print("Step 3: Chat completion (simple API)...")
    try:
        response = client.chat(
            "llama3.2",
            "Say 'Hello from SOLLOL!' in exactly 5 words."
        )
        print(f"Response: {response}")
        print()
    except Exception as e:
        print(f"⚠ Chat failed: {e}")
        print("(Make sure llama3.2 is pulled: ollama pull llama3.2)")
        print()

    # Step 4: Show stats
    stats = client.get_stats()
    print("Step 4: Statistics:")
    print(f"  • Total requests: {stats['total_requests']}")
    print(f"  • Successful: {stats['successful_requests']}")
    print(f"  • Failed: {stats['failed_requests']}")
    print()

    print("=" * 60)
    print("Zero-Config Demo Complete!")
    print()
    print("What just happened:")
    print("1. Auto-discovered Ollama nodes (localhost + network scan)")
    print("2. Created connection pool automatically")
    print("3. Load balanced requests across nodes")
    print("4. All in <1 second, zero configuration")
    print("=" * 60)


if __name__ == "__main__":
    main()
