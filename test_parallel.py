#!/usr/bin/env python3
"""
Quick test for parallel execution with SOLLOL routing.
"""
import sys
import time
from node_registry import NodeRegistry
from distributed_orchestrator import DistributedOrchestrator

def test_parallel():
    """Test parallel execution with multiple nodes."""
    print("🧪 Testing Parallel Execution Engine\n")

    # Create registry
    registry = NodeRegistry()

    # Add your nodes
    print("📡 Adding nodes...")
    registry.add_node("http://10.9.66.154:11434", name="node-154", priority=5)
    registry.add_node("http://10.9.66.157:11434", name="node-157", priority=5)

    print(f"✅ Added {len(registry)} nodes\n")

    # Create orchestrator
    orchestrator = DistributedOrchestrator(registry=registry, use_sollol=True)

    # Run a simple query
    prompt = "Write a haiku about distributed computing"

    print(f"📝 Query: {prompt}\n")
    print("🚀 Starting execution...\n")

    start = time.time()
    result = orchestrator.run(prompt, model="llama3.2")
    duration = time.time() - start

    print(f"\n✅ Execution complete in {duration:.2f}s")
    print(f"\n📊 Metrics:")
    print(f"   Mode: {result['metrics'].get('mode', 'unknown')}")
    print(f"   Nodes used: {result['metrics'].get('nodes_used', 1)}")

    if 'speedup_factor' in result['metrics']:
        print(f"   Speedup: {result['metrics']['speedup_factor']:.2f}x")
        print(f"   Efficiency: {result['metrics']['parallel_efficiency']:.1%}")

    print(f"\n🎯 Node Attribution:")
    for attr in result['metrics'].get('node_attribution', []):
        print(f"   {attr['agent']:12} → {attr['node']:30} ({attr['time']:.2f}s)")

    print(f"\n📝 Result:")
    if 'final_output' in result['result']:
        print(result['result']['final_output'])
    else:
        print(result['result'])

if __name__ == "__main__":
    test_parallel()
