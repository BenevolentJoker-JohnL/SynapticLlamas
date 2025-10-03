#!/usr/bin/env python3
"""
Simple query example - Basic usage of SynapticLlamas
"""

from orchestrator import run_parallel_agents

def main():
    # Simple parallel query
    result = run_parallel_agents(
        input_data="Explain how blockchain technology works",
        model="llama3.2",
        max_workers=3
    )

    # Display results
    print("\n" + "="*70)
    print("FINAL OUTPUT")
    print("="*70)
    print(result['result']['final_output'])
    print("="*70)

    # Show metrics
    print(f"\nTotal time: {result['metrics']['total_execution_time']:.2f}s")
    print(f"Agent count: {result['metrics']['agent_count']}")

if __name__ == "__main__":
    main()
