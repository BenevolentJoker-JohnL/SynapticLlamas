#!/usr/bin/env python3
"""
Custom agent example - Extending SynapticLlamas with custom agents
"""

from agents.base_agent import BaseAgent
from distributed_orchestrator import DistributedOrchestrator
from node_registry import NodeRegistry

class SummarizerAgent(BaseAgent):
    """Custom agent that creates concise summaries"""

    def __init__(self, model="llama3.2", timeout=300):
        super().__init__("Summarizer", model, timeout=timeout)

        # Define JSON schema for TrustCall validation
        self.expected_schema = {
            "summary": str,
            "key_takeaways": list,
            "word_count": int
        }

    def process(self, input_data):
        """Create a concise summary of the input"""
        system_prompt = """You are a professional summarizer.
        Create concise, accurate summaries that capture the essence of the content.
        Output ONLY valid JSON."""

        prompt = f"""Create a concise summary of the following content:

{input_data}

Output a JSON object with:
- summary: A 2-3 sentence summary
- key_takeaways: List of 3-5 key points
- word_count: Approximate word count of summary

Output valid JSON now:"""

        return self.call_ollama(
            prompt,
            system_prompt=system_prompt,
            force_json=True,
            use_trustcall=True
        )


class FactCheckerAgent(BaseAgent):
    """Custom agent that validates factual accuracy"""

    def __init__(self, model="llama3.2", timeout=300):
        super().__init__("FactChecker", model, timeout=timeout)

        self.expected_schema = {
            "claims": list,
            "verified": list,
            "questionable": list,
            "confidence": float
        }

    def process(self, input_data):
        """Check factual accuracy of claims"""
        system_prompt = """You are a fact-checker.
        Identify claims, verify accuracy, and flag questionable statements.
        Output ONLY valid JSON."""

        prompt = f"""Analyze the following content for factual accuracy:

{input_data}

Output a JSON object with:
- claims: List of main factual claims made
- verified: List of claims that are well-established facts
- questionable: List of claims that need more verification
- confidence: Overall confidence in accuracy (0.0-1.0)

Output valid JSON now:"""

        return self.call_ollama(
            prompt,
            system_prompt=system_prompt,
            force_json=True,
            use_trustcall=True
        )


def main():
    # Setup
    registry = NodeRegistry()
    registry.add_node("http://localhost:11434", name="localhost", priority=10)

    # Create custom agents
    summarizer = SummarizerAgent()
    fact_checker = FactCheckerAgent()

    # Sample content to process
    content = """
    Quantum computers use qubits instead of classical bits. Unlike classical bits
    which can be either 0 or 1, qubits can exist in superposition, being both 0
    and 1 simultaneously. This allows quantum computers to process certain types
    of problems exponentially faster than classical computers. Major tech companies
    like IBM, Google, and Microsoft are investing heavily in quantum computing
    research. In 2019, Google claimed to achieve quantum supremacy with their
    Sycamore processor, completing a calculation in 200 seconds that would take
    classical supercomputers thousands of years.
    """

    print("🔧 Using custom agents to process content...")
    print("\n" + "="*70)
    print("ORIGINAL CONTENT")
    print("="*70)
    print(content)
    print("="*70)

    # Use custom summarizer
    print("\n📝 Running Summarizer Agent...")
    summary_result = summarizer.process(content)

    print("\n" + "="*70)
    print("SUMMARIZER OUTPUT")
    print("="*70)
    print(f"Summary: {summary_result['summary']}")
    print(f"\nKey Takeaways:")
    for i, takeaway in enumerate(summary_result['key_takeaways'], 1):
        print(f"  {i}. {takeaway}")
    print(f"\nWord Count: {summary_result['word_count']}")
    print("="*70)

    # Use custom fact checker
    print("\n🔍 Running FactChecker Agent...")
    fact_result = fact_checker.process(content)

    print("\n" + "="*70)
    print("FACT CHECKER OUTPUT")
    print("="*70)
    print(f"Overall Confidence: {fact_result['confidence']:.2f}\n")

    print("Verified Claims:")
    for claim in fact_result['verified']:
        print(f"  ✅ {claim}")

    if fact_result['questionable']:
        print("\nQuestionable Claims:")
        for claim in fact_result['questionable']:
            print(f"  ⚠️  {claim}")

    print("="*70)

    print("\n✨ Custom agents completed successfully!")

if __name__ == "__main__":
    main()
