#!/usr/bin/env python3
"""
Quick Demo: SynapticLlamas Observability

Shows intelligent routing and performance tracking in action.
"""

import logging
import sys

# Configure logging to show observability
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    stream=sys.stdout
)

from sollol import Ollama


def main():
    print("=" * 70)
    print("🧠 SynapticLlamas Observability Demo")
    print("=" * 70)
    print()

    # Create client - auto-discovers and enables intelligent routing
    print("1. Creating zero-config client...")
    client = Ollama()
    print()

    # Make a request - watch the routing decision
    print("2. Making request with intelligent routing:")
    print("   Prompt: 'Summarize quantum computing in one sentence'")
    print()
    response = client.chat(
        "llama3.2",
        "Summarize quantum computing in one sentence"
    )
    print()
    print(f"   Response: {response[:80]}...")
    print()

    # Show performance stats
    print("3. Performance statistics:")
    stats = client.get_stats()
    print(f"   • Intelligent routing: {'✅ Enabled' if stats['intelligent_routing_enabled'] else '❌ Disabled'}")
    print(f"   • Total requests: {stats['total_requests']}")
    print(f"   • Success rate: {stats['successful_requests']}/{stats['total_requests']}")
    print()

    print("   Node performance:")
    for node_key, perf in stats['node_performance'].items():
        print(f"   • {node_key}:")
        print(f"     - Latency: {perf['latency_ms']:.1f}ms")
        print(f"     - Success: {perf['success_rate']:.1%}")
    print()

    print("=" * 70)
    print("✅ Full SynapticLlamas observability - automatically enabled!")
    print("=" * 70)


if __name__ == "__main__":
    main()
