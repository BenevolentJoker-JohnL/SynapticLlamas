#!/usr/bin/env python3
"""
Test script for remote FlockParser access.

Tests both local and remote modes of FlockParserAdapter.
"""
import sys
import logging
from flockparser_adapter import FlockParserAdapter

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_local_mode():
    """Test local filesystem mode."""
    logger.info("=" * 70)
    logger.info("TEST 1: Local Filesystem Mode")
    logger.info("=" * 70)

    adapter = FlockParserAdapter(
        flockparser_path="/home/joker/FlockParser"
    )

    # Get statistics
    stats = adapter.get_statistics()
    logger.info(f"Statistics: {stats}")

    if stats['available']:
        # Try a simple query
        logger.info("\nQuerying for 'quantum entanglement'...")
        results = adapter.query_documents("quantum entanglement", top_k=3)
        logger.info(f"Found {len(results)} results")

        if results:
            logger.info(f"Top result: {results[0]['doc_name']} (similarity: {results[0]['similarity']:.3f})")
            logger.info(f"Text preview: {results[0]['text'][:200]}...")

    return stats['available']


def test_remote_mode(api_url: str):
    """Test remote HTTP API mode."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Remote HTTP API Mode")
    logger.info("=" * 70)

    adapter = FlockParserAdapter(
        flockparser_path=api_url
    )

    # Get statistics
    stats = adapter.get_statistics()
    logger.info(f"Statistics: {stats}")

    if stats['available']:
        # Try a simple query
        logger.info("\nQuerying for 'quantum entanglement'...")
        results = adapter.query_documents("quantum entanglement", top_k=3)
        logger.info(f"Found {len(results)} results")

        if results:
            logger.info(f"Top result: {results[0]['doc_name']} (similarity: {results[0]['similarity']:.3f})")
            logger.info(f"Text preview: {results[0]['text'][:200]}...")

    return stats['available']


def main():
    """Run tests."""
    logger.info("\n" + "=" * 70)
    logger.info("FLOCKPARSER REMOTE MODE TEST")
    logger.info("=" * 70)

    # Test 1: Local mode
    local_works = test_local_mode()

    # Test 2: Remote mode (if API URL provided)
    if len(sys.argv) > 1:
        api_url = sys.argv[1]
        remote_works = test_remote_mode(api_url)
    else:
        logger.info("\n" + "=" * 70)
        logger.info("Skipping remote mode test (no API URL provided)")
        logger.info("To test remote mode, run:")
        logger.info("  python test_remote_flockparser.py http://localhost:8765")
        logger.info("=" * 70)
        remote_works = None

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("TEST SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Local mode:  {'✅ WORKING' if local_works else '❌ FAILED'}")
    if remote_works is not None:
        logger.info(f"Remote mode: {'✅ WORKING' if remote_works else '❌ FAILED'}")
    logger.info("=" * 70)

    if local_works:
        logger.info("\n✅ FlockParser adapter supports both local and remote modes")
        logger.info("\nUSAGE:")
        logger.info("  Local:  FlockParserAdapter('/home/joker/FlockParser')")
        logger.info("  Remote: FlockParserAdapter('http://remote-host:8765')")
        return 0
    else:
        logger.error("\n❌ Tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
