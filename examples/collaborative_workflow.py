#!/usr/bin/env python3
"""
Collaborative workflow example - Demonstrates multi-agent collaboration
"""

from distributed_orchestrator import DistributedOrchestrator
from node_registry import NodeRegistry

def main():
    # Setup
    registry = NodeRegistry()
    registry.add_node("http://localhost:11434", name="localhost", priority=10)

    orchestrator = DistributedOrchestrator(registry)

    # Run with collaborative workflow
    result = orchestrator.run(
        query="Explain the difference between machine learning and deep learning",
        model="llama3.2",
        collaborative=True,
        refinement_rounds=1
    )

    # Display results
    print("\n" + "="*70)
    print("COLLABORATIVE WORKFLOW RESULTS")
    print("="*70)
    print(result['result']['final_output'])
    print("="*70)

    # Show phase timings
    if 'phase_timings' in result['metrics']:
        print("\n📊 Phase Timings:")
        for phase_name, phase_time in result['metrics']['phase_timings']:
            print(f"  {phase_name}: {phase_time:.2f}s")

    # Show metrics
    print(f"\n⏱️  Total time: {result['metrics']['total_execution_time']:.2f}s")
    print(f"🤖 Agent executions: {result['metrics']['agent_count']}")

    # Show node attribution
    if 'node_attribution' in result['metrics']:
        print(f"\n🌐 Node Attribution:")
        for agent, node in result['metrics']['node_attribution'].items():
            print(f"  {agent}: {node}")

if __name__ == "__main__":
    main()
