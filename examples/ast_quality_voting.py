#!/usr/bin/env python3
"""
AST quality voting example - Quality assurance with feedback loops
"""

from distributed_orchestrator import DistributedOrchestrator
from node_registry import NodeRegistry

def main():
    # Setup
    registry = NodeRegistry()
    registry.add_node("http://localhost:11434", name="localhost", priority=10)

    orchestrator = DistributedOrchestrator(registry)

    # Run with AST quality voting enabled
    print("🎯 Running query with AST quality voting...")
    print("Quality threshold: 0.8")
    print("Max retries: 2")
    print()

    result = orchestrator.run(
        query="Explain quantum computing and its practical applications",
        model="llama3.2",
        collaborative=True,
        enable_ast_voting=True,
        quality_threshold=0.8,
        max_quality_retries=2,
        refinement_rounds=1
    )

    # Display results
    print("\n" + "="*70)
    print("AST QUALITY VOTING RESULTS")
    print("="*70)
    print(result['result']['final_output'])
    print("="*70)

    # Show quality scores
    if 'quality_scores' in result['metrics']:
        print("\n🎓 Quality Scores:")
        for score_data in result['metrics']['quality_scores']:
            agent_name = score_data['agent']
            score_val = score_data['score']
            reasoning = score_data['reasoning']
            print(f"\n  {agent_name}: {score_val:.2f}/1.0")
            print(f"  Reasoning: {reasoning}")

    # Show if quality passed
    quality_passed = result['metrics'].get('quality_passed', True)
    quality_retries = result['metrics'].get('quality_retries', 0)

    if quality_passed:
        print(f"\n✅ Quality check PASSED (retries: {quality_retries})")
    else:
        print(f"\n⚠️  Quality check FAILED after {quality_retries} retries")

    # Show phase timings
    if 'phase_timings' in result['metrics']:
        print("\n📊 Phase Timings:")
        for phase_name, phase_time in result['metrics']['phase_timings']:
            print(f"  {phase_name}: {phase_time:.2f}s")

    print(f"\n⏱️  Total time: {result['metrics']['total_execution_time']:.2f}s")

if __name__ == "__main__":
    main()
