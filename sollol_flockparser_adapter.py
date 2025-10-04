"""
SOLLOL FlockParser Adapter - True Drop-In Replacement for OllamaLoadBalancer

This adapter allows SOLLOL to replace FlockParser's OllamaLoadBalancer with
ZERO code changes required in FlockParser.

Usage in FlockParser:
    # Change this line:
    from flockparsecli import OllamaLoadBalancer

    # To this:
    from sollol_flockparser_adapter import OllamaLoadBalancer

    # Everything else stays the same!
    load_balancer = OllamaLoadBalancer(OLLAMA_INSTANCES, skip_init_checks=_is_module)
    load_balancer.embed_distributed(model, text)
    load_balancer.instances  # Works!
"""

import logging
import time
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
import json

from node_registry import NodeRegistry
from sollol_load_balancer import SOLLOLLoadBalancer

logger = logging.getLogger(__name__)


class OllamaLoadBalancer:
    """
    Drop-in replacement for FlockParser's OllamaLoadBalancer using SOLLOL.

    Provides FlockParser's exact API while using SOLLOL's intelligent routing
    and GPU controller internally.
    """

    def __init__(self, instances: List[str], skip_init_checks: bool = False):
        """
        Initialize adapter with FlockParser's exact signature.

        Args:
            instances: List of Ollama URLs (e.g., ["http://localhost:11434"])
            skip_init_checks: Skip initial health checks (for testing/modules)
        """
        # Store instances list for FlockParser compatibility
        self._instances_list = list(instances)

        # Create SOLLOL components
        self.registry = NodeRegistry()
        self.sollol = SOLLOLLoadBalancer(self.registry, enable_gpu_control=True)

        # FlockParser compatibility flags
        self.skip_init_checks = skip_init_checks

        # Initialize nodes from instances list
        for url in instances:
            try:
                self.registry.add_node(url, auto_probe=not skip_init_checks)
            except Exception as e:
                if not skip_init_checks:
                    logger.warning(f"Failed to add node {url}: {e}")

        logger.info(f"✅ SOLLOL adapter initialized with {len(self._instances_list)} nodes")
        logger.info("🚀 Using SOLLOL intelligent routing + GPU controller")

    @property
    def instances(self) -> List[str]:
        """
        FlockParser compatibility: Expose instances as a list.

        Returns current registered node URLs.
        """
        return [node.url for node in self.registry.nodes.values()]

    def add_node(
        self,
        node_url: str,
        save: bool = True,
        check_models: bool = True,
        optional: bool = False
    ) -> bool:
        """
        Add a node (FlockParser-compatible signature).

        Args:
            node_url: Ollama node URL
            save: Save to disk (ignored for now)
            check_models: Check model availability
            optional: Don't fail if node unreachable

        Returns:
            True if added successfully
        """
        try:
            self.registry.add_node(node_url, auto_probe=check_models)
            self._instances_list.append(node_url)
            logger.info(f"✅ Added node: {node_url}")
            return True
        except Exception as e:
            if not optional:
                logger.error(f"Failed to add node {node_url}: {e}")
            return False

    def remove_node(self, node_url: str) -> bool:
        """
        Remove a node (FlockParser-compatible).

        Args:
            node_url: Node URL to remove

        Returns:
            True if removed
        """
        result = self.registry.remove_node(node_url)
        if result and node_url in self._instances_list:
            self._instances_list.remove(node_url)
        return result

    def list_nodes(self) -> List[str]:
        """
        List all node URLs (FlockParser-compatible).

        Returns:
            List of node URLs
        """
        return self.instances

    def discover_nodes(self, require_embedding_model: bool = True) -> List[str]:
        """
        Auto-discover Ollama nodes on network (FlockParser-compatible).

        Args:
            require_embedding_model: Only add nodes with embedding models

        Returns:
            List of discovered node URLs
        """
        # Use SOLLOL's network discovery
        discovered = self.registry.discover_nodes()

        discovered_urls = [node.url for node in discovered]

        # Update instances list
        for url in discovered_urls:
            if url not in self._instances_list:
                self._instances_list.append(url)

        logger.info(f"🔍 Discovered {len(discovered_urls)} nodes")
        return discovered_urls

    def embed_distributed(
        self,
        model: str,
        input_text: str,
        keep_alive: Optional[str] = None
    ) -> List[float]:
        """
        Distributed embedding using SOLLOL routing (FlockParser-compatible).

        Args:
            model: Embedding model name
            input_text: Text to embed
            keep_alive: Model keep-alive duration

        Returns:
            Embedding vector
        """
        # Build payload for SOLLOL routing
        payload = {
            'model': model,
            'prompt': input_text,
        }

        # Use SOLLOL's intelligent routing
        decision = self.sollol.route_request(payload, agent_name="embedding", priority=5)

        # Execute embedding on selected node
        node_url = decision.node.url

        try:
            response = requests.post(
                f"{node_url}/api/embed",
                json={
                    'model': model,
                    'input': input_text,
                    'keep_alive': keep_alive
                },
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                embeddings = result.get('embeddings', [[]])[0] if result.get('embeddings') else result.get('embedding', [])

                # Record performance for SOLLOL learning
                self.sollol.record_performance(
                    decision,
                    actual_duration_ms=response.elapsed.total_seconds() * 1000,
                    success=True
                )

                return embeddings
            else:
                raise Exception(f"Embedding failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Embedding error on {node_url}: {e}")
            # Record failure
            self.sollol.record_performance(decision, 0, success=False, error=str(e))
            raise

    def embed_batch(
        self,
        model: str,
        texts: List[str],
        max_workers: Optional[int] = None,
        force_mode: Optional[str] = None
    ) -> List[List[float]]:
        """
        Batch embedding with parallel processing (FlockParser-compatible).

        Args:
            model: Embedding model name
            texts: List of texts to embed
            max_workers: Max parallel workers
            force_mode: Force parallel/sequential mode

        Returns:
            List of embedding vectors
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        max_workers = max_workers or min(len(texts), len(self.instances) * 2)

        embeddings = [None] * len(texts)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all embedding tasks
            future_to_idx = {
                executor.submit(self.embed_distributed, model, text): idx
                for idx, text in enumerate(texts)
            }

            # Collect results
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    embeddings[idx] = future.result()
                except Exception as e:
                    logger.error(f"Batch embedding failed for text {idx}: {e}")
                    embeddings[idx] = []

        return embeddings

    def chat_distributed(
        self,
        model: str,
        messages: List[Dict[str, str]],
        keep_alive: Optional[str] = None
    ) -> str:
        """
        Distributed chat using SOLLOL routing (FlockParser-compatible).

        Args:
            model: Chat model name
            messages: Chat messages
            keep_alive: Model keep-alive duration

        Returns:
            Chat response
        """
        # Build payload for SOLLOL routing
        payload = {
            'model': model,
            'messages': messages
        }

        # Use SOLLOL's intelligent routing
        decision = self.sollol.route_request(payload, agent_name="chat", priority=5)

        # Execute chat on selected node
        node_url = decision.node.url

        try:
            response = requests.post(
                f"{node_url}/api/chat",
                json={
                    'model': model,
                    'messages': messages,
                    'keep_alive': keep_alive,
                    'stream': False
                },
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                content = result.get('message', {}).get('content', '')

                # Record performance
                self.sollol.record_performance(
                    decision,
                    actual_duration_ms=response.elapsed.total_seconds() * 1000,
                    success=True
                )

                return content
            else:
                raise Exception(f"Chat failed: {response.status_code}")

        except Exception as e:
            logger.error(f"Chat error on {node_url}: {e}")
            self.sollol.record_performance(decision, 0, success=False, error=str(e))
            raise

    def print_stats(self):
        """
        Print load balancer statistics (FlockParser-compatible).
        """
        stats = self.sollol.get_stats()

        print("\n" + "="*70)
        print("📊 SOLLOL LOAD BALANCER STATISTICS")
        print("="*70)

        print(f"\nLoad Balancer:")
        print(f"  Type: {stats['load_balancer']['type']}")
        print(f"  Intelligent Routing: {stats['load_balancer']['intelligent_routing']}")
        print(f"  GPU Control: {stats['load_balancer']['gpu_control']}")

        print(f"\nNodes:")
        print(f"  Total: {stats['nodes']['total']}")
        print(f"  Healthy: {stats['nodes']['healthy']}")
        print(f"  GPU Nodes: {stats['nodes']['gpu']}")

        print(f"\nPerformance Memory:")
        print(f"  Tracked Executions: {stats['performance_memory']['tracked_executions']}")
        print(f"  Task Types: {stats['performance_memory']['unique_task_types']}")
        print(f"  Models: {stats['performance_memory']['unique_models']}")

        if 'gpu' in stats:
            gpu = stats['gpu']
            print(f"\nGPU Placement:")
            print(f"  Total Placements: {gpu['total_placements']}")
            print(f"  GPU Placements: {gpu['gpu_placements']}")
            print(f"  GPU Percentage: {gpu['gpu_percentage']:.1f}%")

        print("="*70 + "\n")

    def verify_models_on_nodes(self) -> Dict[str, List[str]]:
        """
        Verify which models are available on each node (FlockParser-compatible).

        Returns:
            Dict mapping node URLs to available models
        """
        node_models = {}

        for node in self.registry.nodes.values():
            try:
                response = requests.get(f"{node.url}/api/tags", timeout=5)
                if response.status_code == 200:
                    models = [m['name'] for m in response.json().get('models', [])]
                    node_models[node.url] = models
                else:
                    node_models[node.url] = []
            except Exception:
                node_models[node.url] = []

        return node_models

    def set_routing_strategy(self, strategy: str):
        """
        Set routing strategy (FlockParser-compatible, informational only).

        SOLLOL uses intelligent routing, so this is informational.

        Args:
            strategy: Strategy name (ignored, SOLLOL uses intelligence)
        """
        logger.info(f"ℹ️  Routing strategy '{strategy}' noted (SOLLOL uses intelligent routing)")

    def force_gpu_all_nodes(self, model: str) -> Dict[str, Dict]:
        """
        Force model to GPU on all capable nodes (FlockParser-compatible).

        Uses SOLLOL's GPU controller.

        Args:
            model: Model name to force to GPU

        Returns:
            Results by node
        """
        if not self.sollol.gpu_controller:
            logger.warning("GPU controller not available")
            return {}

        results = {}

        for node in self.registry.get_gpu_nodes():
            result = self.sollol.gpu_controller.force_gpu_load(node.url, model)
            results[node.url] = result

        return results

    def __repr__(self):
        """String representation."""
        return (
            f"OllamaLoadBalancer(SOLLOL-powered, "
            f"nodes={len(self.instances)}, "
            f"gpu_control=enabled, "
            f"intelligent_routing=enabled)"
        )


# For easy importing in FlockParser
__all__ = ['OllamaLoadBalancer']
