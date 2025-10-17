"""
Race-to-First (Hedging) Strategy for SOLLOL

Sends the same request to multiple nodes simultaneously and uses whichever
responds first. Dramatically reduces tail latency.

Inspired by Jerry-Terrasse's parallel request approach.

Trade-off:
- Better: Latency (p99 latency reduced by 50-90%)
- Worse: Resource usage (2-3x more requests)

Use when:
- Latency is critical (user-facing queries)
- Resources are available (spare capacity)
- Tail latency is unacceptable

Don't use when:
- Resources are scarce (overloaded cluster)
- Cost matters more than latency
- Background/batch jobs
"""

import asyncio
import logging
import time
import requests
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class HedgeResult:
    """Result from hedged request."""
    winner_node: str
    response: Any
    latency_ms: float
    num_requests_sent: int
    num_responses_received: int
    cancelled_nodes: List[str]


class HedgingStrategy:
    """
    Race-to-first hedging for SOLLOL.

    Sends same request to multiple nodes, uses fastest response.
    """

    def __init__(
        self,
        num_hedges: int = 2,
        hedge_delay_ms: float = 0,
        enable_cancellation: bool = True
    ):
        """
        Initialize hedging strategy.

        Args:
            num_hedges: Number of parallel requests (2-3 recommended)
            hedge_delay_ms: Delay between sending hedges (0 = all at once)
            enable_cancellation: Cancel slower requests after first response
        """
        self.num_hedges = num_hedges
        self.hedge_delay_ms = hedge_delay_ms
        self.enable_cancellation = enable_cancellation

        # Statistics
        self.total_requests = 0
        self.total_hedge_requests = 0
        self.total_wasted_requests = 0
        self.latency_improvements = []

    def hedge_request(
        self,
        nodes: List[str],
        request_fn,
        request_args: Dict[str, Any],
        timeout_ms: float = 30000
    ) -> HedgeResult:
        """
        Send hedged request to multiple nodes, return fastest.

        Args:
            nodes: List of node URLs to try
            request_fn: Function to execute request (e.g., embed_distributed)
            request_args: Arguments for request_fn
            timeout_ms: Timeout for each request

        Returns:
            HedgeResult with winner and stats
        """
        start_time = time.time()

        # Select top N nodes for hedging
        hedge_nodes = nodes[:self.num_hedges]

        logger.info(
            f"🏁 Hedging request across {len(hedge_nodes)} nodes: "
            f"{[n for n in hedge_nodes]}"
        )

        # Execute requests in parallel
        winner_node = None
        winner_response = None
        winner_latency = None
        responses_received = 0

        with ThreadPoolExecutor(max_workers=len(hedge_nodes)) as executor:
            # Submit all hedge requests
            futures = {}
            for i, node_url in enumerate(hedge_nodes):
                # Optional staggered start (hedge delay)
                if i > 0 and self.hedge_delay_ms > 0:
                    time.sleep(self.hedge_delay_ms / 1000.0)

                future = executor.submit(
                    self._execute_request,
                    node_url,
                    request_fn,
                    request_args,
                    timeout_ms
                )
                futures[future] = node_url

            # Wait for first successful response
            for future in as_completed(futures):
                responses_received += 1
                node_url = futures[future]

                try:
                    response, latency = future.result()

                    if winner_node is None:
                        # First successful response wins
                        winner_node = node_url
                        winner_response = response
                        winner_latency = latency

                        logger.info(
                            f"✅ Winner: {node_url} ({latency:.0f}ms) "
                            f"- cancelling {len(hedge_nodes) - responses_received} slower requests"
                        )

                        # Cancel remaining requests (if enabled)
                        if self.enable_cancellation:
                            for f in futures:
                                if f != future and not f.done():
                                    f.cancel()

                        break  # Stop waiting for others

                except Exception as e:
                    logger.warning(f"Hedge request failed on {node_url}: {e}")
                    continue

        # Build result
        if winner_node is None:
            raise Exception("All hedge requests failed")

        total_latency = (time.time() - start_time) * 1000

        cancelled_nodes = [
            url for url in hedge_nodes if url != winner_node
        ]

        result = HedgeResult(
            winner_node=winner_node,
            response=winner_response,
            latency_ms=winner_latency,
            num_requests_sent=len(hedge_nodes),
            num_responses_received=responses_received,
            cancelled_nodes=cancelled_nodes
        )

        # Update statistics
        self.total_requests += 1
        self.total_hedge_requests += len(hedge_nodes)
        self.total_wasted_requests += len(hedge_nodes) - 1

        logger.debug(
            f"📊 Hedge stats: sent={len(hedge_nodes)}, "
            f"received={responses_received}, wasted={len(hedge_nodes) - 1}"
        )

        return result

    def _execute_request(
        self,
        node_url: str,
        request_fn,
        request_args: Dict[str, Any],
        timeout_ms: float
    ) -> Tuple[Any, float]:
        """
        Execute single request with timing.

        Args:
            node_url: Node URL
            request_fn: Request function
            request_args: Request arguments
            timeout_ms: Timeout

        Returns:
            (response, latency_ms)
        """
        start = time.time()

        try:
            # Execute request
            response = request_fn(node_url, **request_args)
            latency = (time.time() - start) * 1000

            return response, latency

        except Exception as e:
            logger.debug(f"Request failed on {node_url}: {e}")
            raise

    def get_stats(self) -> Dict[str, Any]:
        """
        Get hedging statistics.

        Returns:
            Statistics dictionary
        """
        waste_percentage = (
            (self.total_wasted_requests / self.total_hedge_requests * 100)
            if self.total_hedge_requests > 0 else 0
        )

        avg_latency_improvement = (
            sum(self.latency_improvements) / len(self.latency_improvements)
            if self.latency_improvements else 0
        )

        return {
            'total_requests': self.total_requests,
            'total_hedge_requests': self.total_hedge_requests,
            'total_wasted_requests': self.total_wasted_requests,
            'waste_percentage': waste_percentage,
            'avg_latency_improvement_ms': avg_latency_improvement,
            'num_hedges_per_request': self.num_hedges,
        }


class AdaptiveHedging:
    """
    Adaptive hedging that only hedges when latency is critical.

    Uses heuristics to decide when to hedge:
    - Hedge for user-facing queries (low latency tolerance)
    - Don't hedge for batch jobs (high latency tolerance)
    - Adapt based on current cluster load
    """

    def __init__(self, base_strategy: HedgingStrategy):
        """
        Initialize adaptive hedging.

        Args:
            base_strategy: Base hedging strategy
        """
        self.base_strategy = base_strategy
        self.hedge_threshold_ms = 100  # Hedge if expected latency > 100ms

    def should_hedge(
        self,
        task_context,
        estimated_latency_ms: float,
        cluster_load: float
    ) -> bool:
        """
        Decide whether to hedge this request.

        Args:
            task_context: Task context from intelligent router
            estimated_latency_ms: Estimated latency
            cluster_load: Current cluster load (0-1)

        Returns:
            True if should hedge
        """
        # Don't hedge if cluster is overloaded (>80% load)
        if cluster_load > 0.8:
            return False

        # Hedge for high-priority tasks
        if task_context.priority >= 7:
            return True

        # Hedge if estimated latency is high
        if estimated_latency_ms > self.hedge_threshold_ms:
            return True

        # Hedge for complex tasks
        if task_context.complexity == 'complex':
            return True

        return False


def create_hedge_request_wrapper(
    base_url: str,
    endpoint: str,
    payload: Dict[str, Any],
    timeout: float = 30
):
    """
    Create a wrapper function for hedged HTTP requests.

    Args:
        base_url: Will be replaced by hedge nodes
        endpoint: API endpoint (e.g., '/api/embed')
        payload: Request payload
        timeout: Timeout in seconds

    Returns:
        Function that takes node_url and executes request
    """
    def request_fn(node_url: str) -> Any:
        """Execute request on specific node."""
        response = requests.post(
            f"{node_url}{endpoint}",
            json=payload,
            timeout=timeout
        )

        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Request failed: {response.status_code}")

    return request_fn


# Example usage for embedding
def hedge_embed_request(
    nodes: List[str],
    model: str,
    text: str,
    num_hedges: int = 2
) -> HedgeResult:
    """
    Hedge an embedding request across multiple nodes.

    Args:
        nodes: List of node URLs
        model: Embedding model
        text: Text to embed
        num_hedges: Number of parallel requests

    Returns:
        HedgeResult with winning response
    """
    strategy = HedgingStrategy(num_hedges=num_hedges)

    # Create request wrapper
    request_fn = create_hedge_request_wrapper(
        base_url="",
        endpoint="/api/embed",
        payload={
            'model': model,
            'input': text
        }
    )

    # Execute hedged request
    result = strategy.hedge_request(
        nodes=nodes,
        request_fn=request_fn,
        request_args={},
        timeout_ms=30000
    )

    return result


# Example usage for chat
def hedge_chat_request(
    nodes: List[str],
    model: str,
    messages: List[Dict[str, str]],
    num_hedges: int = 2
) -> HedgeResult:
    """
    Hedge a chat request across multiple nodes.

    Args:
        nodes: List of node URLs
        model: Chat model
        messages: Chat messages
        num_hedges: Number of parallel requests

    Returns:
        HedgeResult with winning response
    """
    strategy = HedgingStrategy(num_hedges=num_hedges)

    # Create request wrapper
    request_fn = create_hedge_request_wrapper(
        base_url="",
        endpoint="/api/chat",
        payload={
            'model': model,
            'messages': messages,
            'stream': False
        }
    )

    # Execute hedged request
    result = strategy.hedge_request(
        nodes=nodes,
        request_fn=request_fn,
        request_args={},
        timeout_ms=60000
    )

    return result
