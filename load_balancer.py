import logging
import random
from typing import List, Optional, Dict
from enum import Enum
from ollama_node import OllamaNode
from node_registry import NodeRegistry

logger = logging.getLogger(__name__)


class RoutingStrategy(Enum):
    """Load balancing strategies."""
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    RANDOM = "random"
    PRIORITY = "priority"
    GPU_FIRST = "gpu_first"


class OllamaLoadBalancer:
    """
    Load balancer for Ollama nodes with intelligent routing.
    """

    def __init__(self, registry: NodeRegistry, strategy: RoutingStrategy = RoutingStrategy.LEAST_LOADED):
        """
        Initialize load balancer.

        Args:
            registry: NodeRegistry instance
            strategy: Default routing strategy
        """
        self.registry = registry
        self.strategy = strategy
        self._round_robin_index = 0

    def get_node(self, strategy: Optional[RoutingStrategy] = None,
                 require_gpu: bool = False) -> Optional[OllamaNode]:
        """
        Get next node based on strategy.

        Args:
            strategy: Override default strategy
            require_gpu: Only return GPU nodes

        Returns:
            Selected OllamaNode or None
        """
        strategy = strategy or self.strategy

        # Get candidate nodes
        if require_gpu:
            candidates = self.registry.get_gpu_nodes()
        else:
            candidates = self.registry.get_healthy_nodes()

        if not candidates:
            logger.warning("No available nodes found")
            return None

        # Select based on strategy
        if strategy == RoutingStrategy.ROUND_ROBIN:
            return self._round_robin(candidates)
        elif strategy == RoutingStrategy.LEAST_LOADED:
            return self._least_loaded(candidates)
        elif strategy == RoutingStrategy.RANDOM:
            return random.choice(candidates)
        elif strategy == RoutingStrategy.PRIORITY:
            return self._priority(candidates)
        elif strategy == RoutingStrategy.GPU_FIRST:
            return self._gpu_first(candidates)
        else:
            return self._least_loaded(candidates)

    def get_nodes(self, count: int, strategy: Optional[RoutingStrategy] = None,
                  require_gpu: bool = False) -> List[OllamaNode]:
        """
        Get multiple nodes for parallel execution.

        Args:
            count: Number of nodes to get
            strategy: Routing strategy
            require_gpu: Only return GPU nodes

        Returns:
            List of selected nodes (may be less than count if not enough available)
        """
        strategy = strategy or self.strategy

        if require_gpu:
            candidates = self.registry.get_gpu_nodes()
        else:
            candidates = self.registry.get_healthy_nodes()

        if not candidates:
            return []

        # If requesting more nodes than available, return all
        if count >= len(candidates):
            return candidates

        # Select based on strategy
        if strategy == RoutingStrategy.LEAST_LOADED:
            # Sort by load score and take top N
            sorted_nodes = sorted(candidates, key=lambda n: n.calculate_load_score())
            return sorted_nodes[:count]

        elif strategy == RoutingStrategy.PRIORITY:
            # Sort by priority (descending) and take top N
            sorted_nodes = sorted(candidates, key=lambda n: n.priority, reverse=True)
            return sorted_nodes[:count]

        elif strategy == RoutingStrategy.GPU_FIRST:
            gpu_nodes = [n for n in candidates if n.capabilities.has_gpu]
            cpu_nodes = [n for n in candidates if not n.capabilities.has_gpu]

            # Prefer GPU nodes first
            selected = gpu_nodes[:count]
            if len(selected) < count:
                selected.extend(cpu_nodes[:count - len(selected)])
            return selected

        elif strategy == RoutingStrategy.RANDOM:
            return random.sample(candidates, count)

        else:  # ROUND_ROBIN
            selected = []
            for _ in range(count):
                selected.append(self._round_robin(candidates))
            return selected

    def _round_robin(self, nodes: List[OllamaNode]) -> OllamaNode:
        """Round-robin selection."""
        if not nodes:
            return None

        node = nodes[self._round_robin_index % len(nodes)]
        self._round_robin_index += 1
        return node

    def _least_loaded(self, nodes: List[OllamaNode]) -> OllamaNode:
        """Select node with least load."""
        # Update load scores
        for node in nodes:
            node.calculate_load_score()

        # Return node with minimum load
        return min(nodes, key=lambda n: n.metrics.load_score)

    def _priority(self, nodes: List[OllamaNode]) -> OllamaNode:
        """Select highest priority node."""
        return max(nodes, key=lambda n: n.priority)

    def _gpu_first(self, nodes: List[OllamaNode]) -> OllamaNode:
        """Prefer GPU nodes, then fall back to least loaded."""
        gpu_nodes = [n for n in nodes if n.capabilities.has_gpu]

        if gpu_nodes:
            return self._least_loaded(gpu_nodes)
        else:
            return self._least_loaded(nodes)

    def health_check_loop(self, interval: int = 30):
        """
        Background health check loop (run in separate thread).

        Args:
            interval: Check interval in seconds
        """
        import time

        logger.info(f"🏥 Starting health check loop (interval: {interval}s)")

        while True:
            try:
                self.registry.health_check_all()
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("Health check loop stopped")
                break
            except Exception as e:
                logger.error(f"Health check error: {e}")
                time.sleep(interval)

    def get_stats(self) -> Dict:
        """Get load balancer statistics."""
        all_nodes = list(self.registry.nodes.values())
        healthy = self.registry.get_healthy_nodes()
        gpu = self.registry.get_gpu_nodes()

        total_requests = sum(n.metrics.total_requests for n in all_nodes)
        total_failures = sum(n.metrics.failed_requests for n in all_nodes)

        return {
            "total_nodes": len(all_nodes),
            "healthy_nodes": len(healthy),
            "gpu_nodes": len(gpu),
            "total_requests": total_requests,
            "total_failures": total_failures,
            "failure_rate": total_failures / total_requests if total_requests > 0 else 0,
            "strategy": self.strategy.value,
            "nodes": [n.to_dict() for n in all_nodes]
        }

    def __repr__(self):
        healthy = len(self.registry.get_healthy_nodes())
        return f"LoadBalancer({len(self.registry)} nodes, {healthy} healthy, strategy={self.strategy.value})"
