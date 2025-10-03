#!/usr/bin/env python3
"""
Distributed nodes example - Multi-node orchestration with network discovery
"""

from distributed_orchestrator import DistributedOrchestrator
from node_registry import NodeRegistry

def main():
    # Create registry
    registry = NodeRegistry()

    # Add multiple nodes
    registry.add_node("http://localhost:11434", name="localhost", priority=10)
    registry.add_node("http://192.168.1.100:11434", name="workstation", priority=8)
    registry.add_node("http://192.168.1.101:11434", name="server", priority=9)

    # Discover additional nodes on network
    print("🔍 Discovering nodes on network...")
    discovered = registry.discover_nodes("192.168.1.0/24")
    print(f"✅ Discovered {len(discovered)} nodes")

    # Show all nodes
    print(f"\n📡 Active Nodes ({len(registry)}):")
    for node in registry.get_all_nodes():
        print(f"  • {node.name} - {node.base_url} (priority: {node.priority})")

    # Health check
    print("\n🏥 Health Check:")
    health_results = registry.health_check_all()
    for node_name, is_healthy in health_results.items():
        status = "✅ Healthy" if is_healthy else "❌ Unhealthy"
        print(f"  {node_name}: {status}")

    # Run distributed query
    orchestrator = DistributedOrchestrator(registry)

    print("\n🚀 Running distributed query...")
    result = orchestrator.run(
        query="What are the key principles of distributed systems?",
        model="llama3.2",
        collaborative=True
    )

    # Display results
    print("\n" + "="*70)
    print("DISTRIBUTED QUERY RESULTS")
    print("="*70)
    print(result['result']['final_output'])
    print("="*70)

    # Show which nodes handled which agents
    if 'node_attribution' in result['metrics']:
        print(f"\n🌐 Node Attribution:")
        for agent, node in result['metrics']['node_attribution'].items():
            print(f"  {agent}: {node}")

    print(f"\n⏱️  Total time: {result['metrics']['total_execution_time']:.2f}s")

if __name__ == "__main__":
    main()
