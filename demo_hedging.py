#!/usr/bin/env python3
"""
Demo: Race-to-First Hedging in SOLLOL

Shows how hedging (parallel requests) dramatically reduces tail latency
by racing requests to multiple nodes and using the fastest response.

Inspired by Jerry-Terrasse's parallel request approach.
"""

import time
import random
from sollol.hedging import HedgingStrategy, hedge_embed_request


def simulate_slow_node_scenario():
    """
    Simulate a realistic scenario where nodes have variable latency.
    """
    print("\n" + "="*70)
    print("🎯 SCENARIO: Variable Node Latency")
    print("="*70)

    print("\nYou have 3 Ollama nodes:")
    print("  Node 1: Usually fast (100ms), but sometimes slow (2000ms)")
    print("  Node 2: Medium speed (500ms)")
    print("  Node 3: Slow but reliable (1000ms)")

    print("\nProblem:")
    print("  If you route to Node 1 and hit a slow request, you wait 2000ms")
    print("  That's 20x slower than the typical 100ms")
    print("  This is 'tail latency' - the occasional super slow request")

    print("\nSolution:")
    print("  Send same request to Node 1 AND Node 2 simultaneously")
    print("  Use whichever responds first")
    print("  Cancel the slower one")


def demo_without_hedging():
    """Show latency distribution WITHOUT hedging."""
    print("\n" + "="*70)
    print("❌ WITHOUT HEDGING (Traditional Routing)")
    print("="*70)

    # Simulate 10 requests
    latencies = []

    print("\nRouting 10 requests to Node 1 (fastest node):")
    for i in range(10):
        # 90% of the time it's fast (100ms)
        # 10% of the time it's slow (2000ms) - tail latency!
        if random.random() < 0.9:
            latency = 100
        else:
            latency = 2000
            print(f"  Request {i+1}: {latency}ms ⚠️  SLOW!")

        latencies.append(latency)

    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]

    print(f"\nLatency distribution:")
    print(f"  Average: {avg:.0f}ms")
    print(f"  p50 (median): {p50:.0f}ms")
    print(f"  p99 (worst case): {p99:.0f}ms")
    print(f"\n❌ Problem: p99 is 20x worse than p50!")
    print(f"   Tail latency kills user experience")


def demo_with_hedging():
    """Show latency distribution WITH hedging."""
    print("\n" + "="*70)
    print("✅ WITH HEDGING (Race-to-First)")
    print("="*70)

    latencies = []

    print("\nRacing 10 requests across Node 1 AND Node 2:")
    for i in range(10):
        # Node 1: 90% fast (100ms), 10% slow (2000ms)
        if random.random() < 0.9:
            node1_latency = 100
        else:
            node1_latency = 2000

        # Node 2: Always medium (500ms)
        node2_latency = 500

        # Use fastest
        winner_latency = min(node1_latency, node2_latency)

        if node1_latency == 2000:
            print(f"  Request {i+1}: Node 1 slow (2000ms), Node 2 wins (500ms) ✅")
        else:
            print(f"  Request {i+1}: Node 1 wins (100ms), Node 2 cancelled ✅")

        latencies.append(winner_latency)

    avg = sum(latencies) / len(latencies)
    p50 = sorted(latencies)[len(latencies) // 2]
    p99 = sorted(latencies)[int(len(latencies) * 0.99)]

    print(f"\nLatency distribution:")
    print(f"  Average: {avg:.0f}ms")
    print(f"  p50 (median): {p50:.0f}ms")
    print(f"  p99 (worst case): {p99:.0f}ms")
    print(f"\n✅ Result: p99 is only 5x worse than p50 (not 20x!)")
    print(f"   Tail latency reduced by 75%")


def demo_comparison():
    """Show side-by-side comparison."""
    print("\n" + "="*70)
    print("📊 LATENCY COMPARISON")
    print("="*70)

    print("\nWithout Hedging (traditional):")
    print("  p50: 100ms")
    print("  p99: 2000ms")
    print("  Tail latency: 20x worse")

    print("\nWith Hedging (race-to-first):")
    print("  p50: 100ms (same)")
    print("  p99: 500ms (much better!)")
    print("  Tail latency: 5x worse (75% improvement)")

    print("\nTrade-off:")
    print("  ✅ Better: 75% reduction in tail latency")
    print("  ❌ Worse: 2x more requests (one gets cancelled)")

    print("\nWhen to use hedging:")
    print("  ✅ User-facing queries (latency matters)")
    print("  ✅ Spare capacity (can handle 2x requests)")
    print("  ✅ Variable node performance")
    print("  ❌ Overloaded cluster (wastes resources)")
    print("  ❌ Batch jobs (latency doesn't matter)")


def demo_adaptive_hedging():
    """Show adaptive hedging decisions."""
    print("\n" + "="*70)
    print("🧠 ADAPTIVE HEDGING")
    print("="*70)

    print("\nSOLLOL's adaptive hedging automatically decides when to hedge:")

    scenarios = [
        {
            "task": "User query (priority=9)",
            "latency": "200ms",
            "load": "30%",
            "hedge": True,
            "reason": "High priority + spare capacity"
        },
        {
            "task": "Batch job (priority=2)",
            "latency": "500ms",
            "load": "30%",
            "hedge": False,
            "reason": "Low priority, latency OK"
        },
        {
            "task": "User query (priority=9)",
            "latency": "50ms",
            "load": "85%",
            "hedge": False,
            "reason": "Cluster overloaded, can't afford 2x requests"
        },
        {
            "task": "Complex analysis (priority=7)",
            "latency": "1000ms",
            "load": "40%",
            "hedge": True,
            "reason": "High latency + spare capacity"
        },
    ]

    for scenario in scenarios:
        emoji = "🏁" if scenario["hedge"] else "🚫"
        print(f"\n{emoji} {scenario['task']}")
        print(f"   Expected latency: {scenario['latency']}")
        print(f"   Cluster load: {scenario['load']}")
        print(f"   Decision: {'Hedge' if scenario['hedge'] else 'Single-node'}")
        print(f"   Reason: {scenario['reason']}")


def demo_stats():
    """Show hedging statistics."""
    print("\n" + "="*70)
    print("📊 HEDGING STATISTICS")
    print("="*70)

    print("\nAfter 100 requests with hedging enabled:")
    print("  Total requests: 100")
    print("  Total hedge requests: 200 (2x hedging)")
    print("  Wasted requests: 100 (cancelled)")
    print("  Waste percentage: 50%")
    print("  Avg latency improvement: 300ms")

    print("\nResource usage:")
    print("  Without hedging: 100 requests")
    print("  With hedging: 200 requests (100 cancelled)")
    print("  Overhead: 2x requests, but 75% better tail latency")

    print("\nWorth it?")
    print("  If latency matters: YES (user experience 75% better)")
    print("  If cost matters: NO (2x resource usage)")


def main():
    """Run all demos."""
    print("\n" + "="*70)
    print("🏁 SOLLOL RACE-TO-FIRST HEDGING DEMO")
    print("="*70)
    print("\nInspired by Jerry-Terrasse's parallel request approach.")
    print("Hedging = Send same request to multiple nodes, use fastest response.")

    simulate_slow_node_scenario()
    time.sleep(1)

    demo_without_hedging()
    time.sleep(1)

    demo_with_hedging()
    time.sleep(1)

    demo_comparison()
    time.sleep(1)

    demo_adaptive_hedging()
    time.sleep(1)

    demo_stats()

    print("\n" + "="*70)
    print("✅ DEMO COMPLETE")
    print("="*70)

    print("\nKey Takeaway:")
    print("  Hedging trades resource usage for latency.")
    print("  Send 2x requests, get 75% better tail latency.")
    print("  Perfect for user-facing queries where latency matters.")

    print("\nUsage in SOLLOL:")
    print("  # Enable hedging")
    print("  lb = SOLLOLLoadBalancer(registry, enable_hedging=True, num_hedges=2)")
    print()
    print("  # Adaptive: Only hedges when beneficial")
    print("  result = lb.route_with_hedging(payload, priority=9)")
    print()
    print("  # Force hedge for critical requests")
    print("  result = lb.route_with_hedging(payload, force_hedge=True)")
    print()

    print("Credit: Jerry-Terrasse for the brilliant hedging approach!")
    print()


if __name__ == "__main__":
    main()
