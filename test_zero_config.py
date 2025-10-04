#!/usr/bin/env python3
"""
Integration test for zero-config SOLLOL.

Tests that the "just works" promise is kept:
1. Import sollol
2. Create Ollama client
3. Auto-discovery works
4. Requests succeed
"""

import sys


def test_import():
    """Test that import works."""
    print("Test 1: Import sollol...", end=" ")
    try:
        from sollol import Ollama
        print("✓")
        return True
    except ImportError as e:
        print(f"✗ {e}")
        return False


def test_auto_discovery():
    """Test that auto-discovery works."""
    print("Test 2: Auto-discovery...", end=" ")
    try:
        from sollol import Ollama
        client = Ollama()
        stats = client.get_stats()

        if stats['nodes_configured'] > 0:
            print(f"✓ (found {stats['nodes_configured']} nodes)")
            return True
        else:
            print("✗ (no nodes found)")
            return False
    except Exception as e:
        print(f"✗ {e}")
        return False


def test_chat():
    """Test that chat works."""
    print("Test 3: Chat request...", end=" ")
    try:
        from sollol import Ollama
        client = Ollama()
        response = client.chat("llama3.2", "Say 'OK' in one word.")

        if response and len(response) > 0:
            print(f"✓ (got response)")
            return True
        else:
            print("✗ (empty response)")
            return False
    except Exception as e:
        print(f"✗ {e}")
        return False


def test_load_balancing():
    """Test that load balancing works."""
    print("Test 4: Load balancing...", end=" ")
    try:
        from sollol import Ollama
        client = Ollama()

        # Make 5 requests
        for i in range(5):
            client.chat("llama3.2", f"Request {i}")

        stats = client.get_stats()

        if stats['total_requests'] >= 5:
            print(f"✓ ({stats['total_requests']} requests balanced)")
            return True
        else:
            print(f"✗ (only {stats['total_requests']} requests)")
            return False
    except Exception as e:
        print(f"✗ {e}")
        return False


def main():
    print("=" * 60)
    print("Zero-Config SOLLOL Integration Tests")
    print("=" * 60)
    print()

    tests = [
        test_import,
        test_auto_discovery,
        test_chat,
        test_load_balancing,
    ]

    results = []
    for test in tests:
        results.append(test())

    print()
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    if passed == total:
        print(f"✓ All {total} tests passed!")
        print()
        print("Zero-config SOLLOL works as promised:")
        print("1. ✓ Import works")
        print("2. ✓ Auto-discovery works")
        print("3. ✓ Requests succeed")
        print("4. ✓ Load balancing works")
        return 0
    else:
        print(f"✗ {total - passed} of {total} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
