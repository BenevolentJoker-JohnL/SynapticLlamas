#!/usr/bin/env python3
import sys
sys.path.insert(0, ".")
from agents.base_agent import preprocess_llama32_response
import json

# Simulate a 3500 char response with JSON
long_content = "Quantum entanglement is a fundamental phenomenon in quantum mechanics. " * 50  # ~3500 chars

test_input = f'{{"context": "{long_content}"}}'

print(f"Testing full content preservation...")
print(f"Input length: {len(test_input)} chars")
print(f"Content in input: {len(long_content)} chars")

result = preprocess_llama32_response(test_input, {"context": str}, "TestAgent")
parsed = json.loads(result)

output_len = len(parsed["context"])
loss = len(long_content) - output_len
loss_pct = 100 * loss / len(long_content)

print(f"Output context length: {output_len} chars")
print(f"Loss: {loss} chars ({loss_pct:.1f}%)")

if loss == 0:
    print("✅ Perfect preservation - no data loss!")
elif loss_pct < 5:
    print(f"✅ Acceptable loss - less than 5%")
else:
    print(f"❌ Significant loss - {loss_pct:.1f}% of content lost")
