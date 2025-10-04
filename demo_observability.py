#!/usr/bin/env python3
"""
Demo: Full SynapticLlamas Observability in Zero-Config Client

Shows how SOLLOL provides complete observability automatically:
- Intelligent task detection
- Smart routing decisions with reasoning
- Performance tracking and learning
- Detailed logging of all decisions
"""

import logging
import sys

# Configure logging to show observability
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stdout
)

from sollol import Ollama


def demo_task_detection():
    """Show how SOLLOL detects different task types."""
    print("=" * 70)
    print("DEMO 1: Intelligent Task Detection")
    print("=" * 70)
    print()

    client = Ollama()

    tasks = [
        ("Summarize this: AI is transforming industries", "summarization"),
        ("Classify this sentiment: I love this product!", "classification"),
        ("Extract the key entities from: Apple CEO Tim Cook announced...", "extraction"),
        ("Generate a creative story about a robot", "generation"),
    ]

    for prompt, expected_type in tasks:
        print(f"\n📝 Prompt: {prompt[:50]}...")
        print(f"Expected task type: {expected_type}")
        print()

        response = client.chat("llama3.2", prompt)
        print(f"✅ Response received\n")


def demo_performance_tracking():
    """Show how SOLLOL tracks and learns from performance."""
    print("\n" + "=" * 70)
    print("DEMO 2: Performance Tracking & Learning")
    print("=" * 70)
    print()

    client = Ollama()

    print("Making multiple requests to observe learning...\n")

    for i in range(3):
        print(f"Request {i+1}:")
        response = client.chat("llama3.2", f"Tell me fact {i+1} about AI")
        print()

    # Show accumulated stats
    stats = client.get_stats()
    print("\n📊 Performance Statistics:")
    print(f"  Total requests: {stats['total_requests']}")
    print(f"  Successful: {stats['successful_requests']}")
    print(f"  Failed: {stats['failed_requests']}")
    print(f"  Intelligent routing: {'✅ Enabled' if stats['intelligent_routing_enabled'] else '❌ Disabled'}")
    print()

    print("📈 Node Performance:")
    for node_key, perf in stats['node_performance'].items():
        print(f"  {node_key}:")
        print(f"    - Latency: {perf['latency_ms']:.1f}ms")
        print(f"    - Success rate: {perf['success_rate']:.1%}")
        print(f"    - Total requests: {perf['total_requests']}")


def demo_routing_decisions():
    """Show detailed routing decisions."""
    print("\n" + "=" * 70)
    print("DEMO 3: Routing Decision Explanations")
    print("=" * 70)
    print()

    client = Ollama()

    # Complex task that requires GPU
    print("🎯 Complex task (should prefer GPU):")
    response = client.chat(
        "llama3.2",
        "Write a detailed analysis of how neural networks learn through backpropagation"
    )
    print()

    # Simple task
    print("🎯 Simple task:")
    response = client.chat("llama3.2", "Say hello")
    print()


def main():
    print("🧠 SynapticLlamas Full Observability Demo")
    print("=" * 70)
    print()
    print("This demo shows how SOLLOL provides complete observability")
    print("automatically - no configuration needed!")
    print()

    demo_task_detection()
    demo_performance_tracking()
    demo_routing_decisions()

    print("\n" + "=" * 70)
    print("✅ Demo Complete!")
    print()
    print("Key Takeaways:")
    print("1. ✅ Task type detection is automatic")
    print("2. ✅ Routing decisions are logged with reasoning")
    print("3. ✅ Performance is tracked and learned from")
    print("4. ✅ All metrics are available via get_stats()")
    print()
    print("This is the same observability as the full SynapticLlamas,")
    print("but with zero configuration - just import and use!")
    print("=" * 70)


if __name__ == "__main__":
    main()
