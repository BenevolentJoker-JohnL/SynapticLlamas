#!/usr/bin/env python3
"""
Test script to verify citation preservation and LaTeX rendering fixes.
"""
import asyncio
import logging
from distributed_orchestrator import DistributedOrchestrator
from agents.base_agent import clean_broken_latex

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_latex_cleaning():
    """Test the LaTeX cleaning function."""
    logger.info("=" * 70)
    logger.info("TEST 1: LaTeX Cleaning Function")
    logger.info("=" * 70)

    test_cases = [
        ("|psi = sqrt(1/2) * (|00rangle |11rangle)", "|ψ⟩ = √(1/2) * (|00⟩ + |11⟩)"),
        ("|phi = |00rangle", "|φ⟩ = |00⟩"),
        ("The wave function psi describes states", "The wave function ψ describes states"),
        ("entanglement is important", "entanglement is important"),  # Should NOT break "angle"
    ]

    all_passed = True
    for input_text, expected in test_cases:
        result = clean_broken_latex(input_text)
        passed = result == expected
        all_passed = all_passed and passed

        status = "✅ PASS" if passed else "❌ FAIL"
        logger.info(f"{status}")
        logger.info(f"  Input:    {input_text}")
        logger.info(f"  Expected: {expected}")
        logger.info(f"  Got:      {result}")
        logger.info("")

    return all_passed


async def test_citation_preservation():
    """Test citation preservation in synthesis."""
    logger.info("=" * 70)
    logger.info("TEST 2: Citation Preservation in Synthesis")
    logger.info("=" * 70)

    # Initialize orchestrator
    logger.info("Initializing orchestrator...")
    orchestrator = DistributedOrchestrator(
        model="llama3.2",
        enable_collaborative=True,
        use_distributed=True
    )

    # Run a short research query
    query = "Explain quantum entanglement in 100 words"
    logger.info(f"Running query: {query}")
    logger.info("")

    try:
        result = await orchestrator.run_collaborative(query)

        # Check if citations are present in final output
        has_citations = '[1]' in str(result) or '[2]' in str(result) or '[3]' in str(result)

        logger.info("=" * 70)
        logger.info("CITATION PRESERVATION TEST RESULT")
        logger.info("=" * 70)
        logger.info(f"Citations found in output: {'✅ YES' if has_citations else '❌ NO'}")

        # Show a snippet of the output
        output_str = str(result)[:500]
        logger.info(f"\nFirst 500 chars of output:\n{output_str}...")

        return has_citations

    except Exception as e:
        logger.error(f"Test failed with error: {e}")
        return False


def main():
    """Run all tests."""
    logger.info("\n" + "=" * 70)
    logger.info("CITATION AND LATEX FIX VERIFICATION")
    logger.info("=" * 70 + "\n")

    # Test 1: LaTeX cleaning
    latex_test_passed = test_latex_cleaning()

    # Test 2: Citation preservation (async)
    logger.info("\nRunning citation preservation test...")
    logger.info("(This will take ~60-120 seconds with real inference)\n")

    citation_test_passed = asyncio.run(test_citation_preservation())

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"LaTeX Cleaning:        {'✅ PASSED' if latex_test_passed else '❌ FAILED'}")
    logger.info(f"Citation Preservation: {'✅ PASSED' if citation_test_passed else '❌ FAILED'}")
    logger.info("=" * 70)

    if latex_test_passed and citation_test_passed:
        logger.info("\n🎉 ALL TESTS PASSED!")
        return 0
    else:
        logger.info("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
