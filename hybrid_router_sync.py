"""
Synchronous wrapper for HybridRouter to enable RPC sharding in sync agent code.
"""
import asyncio
import threading
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)


class HybridRouterSync:
    """Synchronous wrapper around async HybridRouter."""

    def __init__(self, hybrid_router):
        """
        Args:
            hybrid_router: The async HybridRouter instance
        """
        self.hybrid_router = hybrid_router
        self._loop = None
        self._thread = None
        self._start_event_loop()

    def _start_event_loop(self):
        """Start a dedicated event loop in a background thread."""
        def run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=run_loop, args=(self._loop,), daemon=True)
        self._thread.start()
        logger.info("🔄 HybridRouterSync: Background event loop started")

    def route_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Synchronous wrapper for HybridRouter.route_request().

        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            **kwargs: Additional arguments

        Returns:
            Response dict from the model
        """
        if not self.hybrid_router:
            raise RuntimeError("No HybridRouter available")

        # Schedule the async call in the background loop and wait for result
        future = asyncio.run_coroutine_threadsafe(
            self.hybrid_router.route_request(model=model, messages=messages, **kwargs),
            self._loop
        )

        # Block until result is ready (with timeout from kwargs if provided)
        timeout = kwargs.get('timeout', 300)
        try:
            result = future.result(timeout=timeout)
            return result
        except Exception as e:
            logger.error(f"HybridRouter request failed: {e}")
            raise

    def __del__(self):
        """Cleanup the event loop."""
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
