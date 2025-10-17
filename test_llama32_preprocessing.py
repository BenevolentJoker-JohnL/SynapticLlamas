#!/usr/bin/env python3
"""
Test script for llama3.2 preprocessing function.
"""

import sys
import json
sys.path.insert(0, '.')

from agents.base_agent import preprocess_llama32_response

# Test schema similar to what Researcher uses
test_schema = {
    "context": str
}

# Test cases
test_cases = [
    {
        "name": "Literal schema copy",
        "input": '{"context": str}',
        "expected_behavior": "Should detect literal schema and return minimal JSON"
    },
    {
        "name": "Markdown wrapped JSON",
        "input": '''```json
{"context": "Quantum entanglement is a physical phenomenon that occurs when pairs of particles become correlated in such a way that the quantum state of each particle cannot be described independently."}
```''',
        "expected_behavior": "Should strip markdown and return valid JSON"
    },
    {
        "name": "Mixed text and JSON",
        "input": '''Here's the answer:

Quantum entanglement is a physical phenomenon that occurs when pairs of particles become correlated in such a way that the quantum state of each particle cannot be described independently.

{"context": "Some content"}''',
        "expected_behavior": "Should extract the substantive text content"
    },
    {
        "name": "Valid JSON",
        "input": '{"context": "Quantum entanglement is a physical phenomenon that occurs when pairs of particles become correlated in such a way that the quantum state of each particle cannot be described independently."}',
        "expected_behavior": "Should pass through unchanged"
    },
    {
        "name": "Text with no JSON",
        "input": '''Quantum entanglement is a physical phenomenon that occurs when pairs of particles become correlated in such a way that the quantum state of each particle cannot be described independently. This effect is at the heart of many quantum technologies and has been experimentally verified countless times.''',
        "expected_behavior": "Should extract text and force into schema"
    }
]

print("Testing llama3.2 preprocessing function")
print("=" * 80)

for i, test_case in enumerate(test_cases, 1):
    print(f"\nTest {i}: {test_case['name']}")
    print(f"Expected: {test_case['expected_behavior']}")
    print(f"\nInput ({len(test_case['input'])} chars):")
    print(test_case['input'][:200] + "..." if len(test_case['input']) > 200 else test_case['input'])

    try:
        result = preprocess_llama32_response(
            test_case['input'],
            test_schema,
            "TestAgent"
        )

        # Try to parse result as JSON
        parsed = json.loads(result)

        print(f"\n✅ Output (valid JSON):")
        print(json.dumps(parsed, indent=2))

        # Check if context field exists and has content
        if 'context' in parsed:
            content_length = len(parsed['context']) if isinstance(parsed['context'], str) else 0
            print(f"\nContext field: {content_length} chars")
            if content_length > 0:
                preview = parsed['context'][:150] + "..." if len(parsed['context']) > 150 else parsed['context']
                print(f"Preview: {preview}")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("-" * 80)

print("\nAll tests completed!")
