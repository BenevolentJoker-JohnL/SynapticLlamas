#!/usr/bin/env python3
"""
Test the fixed warm_model() method in OllamaPool.
"""
import sys
sys.path.insert(0, '/home/joker/.local/lib/python3.10/site-packages')

from sollol.pool import OllamaPool

def test_warm_model():
    print("=" * 70)
    print("Testing Fixed warm_model() Method")
    print("=" * 70)

    # Create pool
    print("\n1. Creating OllamaPool...")
    pool = OllamaPool.auto_configure(register_with_dashboard=False)
    print(f"✓ Pool created with {len(pool.nodes)} nodes")

    # Test warming a single model on all nodes
    print("\n2. Testing warm_model() with llama3.2:latest...")
    success = pool.warm_model("llama3.2:latest")

    if success:
        print("✓ warm_model() succeeded!")
    else:
        print("✗ warm_model() failed!")

    # Test warming multiple models
    print("\n3. Testing warm_models() with multiple models...")
    results = pool.warm_models(["llama3.2:3b", "codellama:latest"], parallel=True)

    print("\nResults:")
    for model, success in results.items():
        status = "✓" if success else "✗"
        print(f"  {status} {model}: {'SUCCESS' if success else 'FAILED'}")

    # Summary
    total_success = sum(1 for v in results.values() if v)
    total_models = len(results)

    print(f"\n{'=' * 70}")
    print(f"Test Summary: {total_success}/{total_models} models warmed successfully")
    print(f"{'=' * 70}")

    # Cleanup
    pool.stop()

if __name__ == "__main__":
    test_warm_model()
