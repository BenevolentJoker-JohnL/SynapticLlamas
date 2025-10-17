#!/usr/bin/env python3
"""
Quick verification script for citation and LaTeX fixes.
"""
import re
from agents.base_agent import clean_broken_latex

print("=" * 70)
print("VERIFICATION: Citation & LaTeX Fixes (2025-10-16)")
print("=" * 70)
print()

# Test 1: LaTeX Cleaning Function
print("TEST 1: LaTeX Cleaning Function")
print("-" * 70)

test_cases = [
    {
        "input": "|psi = sqrt(1/2) * (|00rangle |11rangle)",
        "expected_contains": ["ψ", "√", "⟩"],
        "should_not_contain": ["rangle", "psi "],
        "description": "Quantum ket notation with Bell state"
    },
    {
        "input": "|phi = |00rangle + |11rangle",
        "expected_contains": ["φ⟩", "|00⟩", "|11⟩"],
        "should_not_contain": ["rangle"],
        "description": "Phi symbol and ket brackets"
    },
    {
        "input": "The wave function |psi describes quantum states",
        "expected_contains": ["ψ⟩"],
        "should_not_contain": ["|psi"],
        "description": "Greek letter replacement in ket notation"
    },
    {
        "input": "Quantum entanglement is a fundamental phenomenon",
        "expected_contains": ["entanglement"],
        "should_not_contain": ["entalment"],  # Make sure we don't break "angle" in "entanglement"
        "description": "Preserve 'angle' in words like 'entanglement'"
    }
]

latex_passed = 0
latex_failed = 0

for i, test in enumerate(test_cases, 1):
    result = clean_broken_latex(test["input"])
    passed = True

    # Check expected contains
    for expected in test["expected_contains"]:
        if expected not in result:
            passed = False
            print(f"❌ TEST {i} FAILED: {test['description']}")
            print(f"   Expected to find: '{expected}'")
            print(f"   Input:  {test['input']}")
            print(f"   Output: {result}")
            print()
            break

    # Check should not contain
    if passed:
        for unwanted in test["should_not_contain"]:
            if unwanted in result:
                passed = False
                print(f"❌ TEST {i} FAILED: {test['description']}")
                print(f"   Should NOT contain: '{unwanted}'")
                print(f"   Input:  {test['input']}")
                print(f"   Output: {result}")
                print()
                break

    if passed:
        print(f"✅ TEST {i} PASSED: {test['description']}")
        print(f"   Input:  {test['input']}")
        print(f"   Output: {result}")
        print()
        latex_passed += 1
    else:
        latex_failed += 1

print()
print("TEST 2: Citation Preservation in Synthesis Prompt")
print("-" * 70)

# Read distributed_orchestrator.py to verify the fix
try:
    with open('distributed_orchestrator.py', 'r') as f:
        content = f.read()

    # Check for the citation preservation instruction in synthesis prompt
    citation_fix_present = False
    preserve_all_citations = False

    # Look for the synthesis prompt area (around line 1466)
    if 'PRESERVE ALL CITATIONS' in content:
        citation_fix_present = True
        print("✅ Found 'PRESERVE ALL CITATIONS' in synthesis prompt")

    if 'Keep citation markers [1], [2], [3]' in content:
        preserve_all_citations = True
        print("✅ Found explicit citation marker preservation instruction")

    if 'PRESERVE ALL CONTENT AND CITATIONS' in content:
        print("✅ Found 'PRESERVE ALL CONTENT AND CITATIONS' in JSON format")

    print()

    if citation_fix_present and preserve_all_citations:
        print("✅ Citation preservation fix: VERIFIED")
        citation_passed = True
    else:
        print("❌ Citation preservation fix: NOT FOUND")
        citation_passed = False

except Exception as e:
    print(f"❌ Error reading distributed_orchestrator.py: {e}")
    citation_passed = False

print()
print("=" * 70)
print("SUMMARY")
print("=" * 70)
print(f"LaTeX Cleaning Tests:      {latex_passed}/{latex_passed + latex_failed} passed")
print(f"Citation Fix Verification: {'✅ VERIFIED' if citation_passed else '❌ FAILED'}")
print()

if latex_passed == len(test_cases) and citation_passed:
    print("🎉 ALL VERIFICATIONS PASSED!")
    print()
    print("NEXT STEPS:")
    print("- Run a live test with: python main.py --interactive --distributed")
    print("- Try query: 'Explain quantum entanglement'")
    print("- Check for:")
    print("  1. Proper LaTeX symbols (ψ, ⟩, √) in output")
    print("  2. Citation markers [1], [2], [3] in final text")
    exit(0)
else:
    print("❌ SOME VERIFICATIONS FAILED")
    exit(1)
