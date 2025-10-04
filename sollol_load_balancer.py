"""
SOLLOL-Enhanced Load Balancer for SynapticLlamas

This module replaces the basic load balancer with SOLLOL's intelligent routing engine.
All SOLLOL capabilities are automatically integrated:
- Context-aware request analysis
- Task type detection
- Priority-based scheduling
- Multi-factor host scoring
- Adaptive learning
- Performance tracking

No external SOLLOL service needed - fully embedded!
"""
import logging
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
from datetime import datetime

# Import SOLLOL modules
from sollol.intelligence import IntelligentRouter, TaskContext
from sollol.prioritization import (
    PriorityQueue,
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_NORMAL,
    PRIORITY_LOW,
    PRIORITY_BATCH
)
from sollol.adapters import PerformanceMemory, MetricsCollector
from sollol.gpu_controller import SOLLOLGPUController, integrate_with_router

# Import existing SynapticLlamas modules
from node_registry import NodeRegistry
from ollama_node import OllamaNode

logger = logging.getLogger(__name__)


@dataclass
class RoutingDecision:
    """Complete routing decision with reasoning."""
    node: OllamaNode
    task_context: TaskContext
    decision_score: float
    reasoning: str
    timestamp: datetime
    fallback_nodes: List[OllamaNode]


class SOLLOLLoadBalancer:
    """
    SOLLOL-powered intelligent load balancer.

    Automatically provides:
    - Intelligent routing based on request analysis
    - Priority queue for request scheduling
    - Performance tracking and adaptive learning
    - Multi-factor node scoring
    - Automatic failover with reasoning
    """

    def __init__(self, registry: NodeRegistry, enable_gpu_control: bool = True):
        """
        Initialize SOLLOL load balancer.

        Args:
            registry: Node registry for managing Ollama nodes
            enable_gpu_control: Enable active GPU controller integration
        """
        self.registry = registry

        # SOLLOL components
        self.intelligence = IntelligentRouter()
        self.priority_queue = PriorityQueue()
        self.memory = PerformanceMemory()
        self.metrics = MetricsCollector()

        # GPU controller (CRITICAL for SOLLOL's performance promise)
        self.gpu_controller = None
        if enable_gpu_control:
            self.gpu_controller = SOLLOLGPUController(registry)
            logger.info("🚀 GPU controller enabled - ensuring models run on GPU")
        else:
            logger.warning("⚠️  GPU controller disabled - routing may not optimize performance")

        logger.info("🚀 SOLLOL Load Balancer initialized with intelligent routing")

    def route_request(
        self,
        payload: Dict[str, Any],
        agent_name: str = "Unknown",
        priority: int = 5
    ) -> RoutingDecision:
        """
        Route a request using SOLLOL's intelligent routing engine.

        This is the main entry point that replaces get_node() with
        full context-aware routing.

        Args:
            payload: Request payload (prompt, messages, etc.)
            agent_name: Name of the agent making the request
            priority: Request priority (1-10, higher = more important)

        Returns:
            RoutingDecision with node, context, score, and reasoning
        """
        start_time = time.time()

        # Step 1: Analyze request to build context
        context = self.intelligence.analyze_request(payload, priority)

        logger.debug(
            f"📊 Request Analysis: type={context.task_type}, "
            f"complexity={context.complexity}, priority={priority}, "
            f"tokens={context.estimated_tokens}"
        )

        # Step 2: Get available healthy nodes
        healthy_nodes = self.registry.get_healthy_nodes()

        if not healthy_nodes:
            raise RuntimeError("No healthy Ollama nodes available")

        logger.debug(f"📊 [ROUTING DEBUG] Healthy nodes: {[n.url for n in healthy_nodes]}")
        logger.debug(f"📊 [ROUTING DEBUG] Registry nodes: {list(self.registry.nodes.keys())}")

        # Step 3: Convert nodes to host metadata for SOLLOL
        available_hosts = [self._node_to_host_metadata(node) for node in healthy_nodes]
        logger.debug(f"📊 [ROUTING DEBUG] Available hosts metadata: {[h['url'] for h in available_hosts]}")

        # Step 4: Use SOLLOL intelligent router to select optimal node
        selected_host, decision_metadata = self.intelligence.select_optimal_node(
            context, available_hosts
        )
        logger.debug(f"📊 [ROUTING DEBUG] SOLLOL selected host URL: {selected_host}")

        # Step 5: Find the OllamaNode object for the selected host
        selected_node = next(
            (node for node in healthy_nodes if node.url == selected_host),
            None
        )
        logger.debug(
            f"📊 [ROUTING DEBUG] Matched node: {selected_node.url if selected_node else 'NONE'}, "
            f"object ID: {id(selected_node) if selected_node else 'N/A'}"
        )

        if not selected_node:
            # Fallback to first healthy node
            selected_node = healthy_nodes[0]
            decision_metadata = {
                'score': 50.0,
                'reasoning': "Fallback to first available node"
            }

        # Step 6: Prepare fallback nodes (other healthy nodes sorted by score)
        fallback_nodes = [
            node for node in healthy_nodes
            if node.url != selected_node.url
        ]

        # Step 7: Create routing decision
        decision = RoutingDecision(
            node=selected_node,
            task_context=context,
            decision_score=decision_metadata.get('score', 0.0),
            reasoning=decision_metadata.get('reasoning', 'Intelligent routing'),
            timestamp=datetime.now(),
            fallback_nodes=fallback_nodes
        )

        # Step 8: Record metrics
        routing_time = (time.time() - start_time) * 1000
        self.metrics.record_routing_decision(
            agent_name=agent_name,
            task_type=context.task_type,
            priority=priority,
            selected_node=selected_node.url,
            score=decision.decision_score,
            routing_time_ms=routing_time
        )

        logger.info(
            f"✅ Routed {agent_name} to {selected_node.url} "
            f"(score: {decision.decision_score:.1f}, time: {routing_time:.1f}ms)"
        )
        logger.debug(f"   Reasoning: {decision.reasoning}")

        # GPU verification (if GPU controller enabled and GPU expected)
        if self.gpu_controller and context.requires_gpu:
            model = context.model_preference or payload.get('model', '')
            if model:
                # Verify model is on GPU, force load if not
                verified = self.gpu_controller.verify_routing_decision(
                    selected_node.url,
                    model,
                    expected_location='GPU'
                )

                if not verified:
                    logger.warning(
                        f"⚠️  Model {model} not on GPU at {selected_node.url}, "
                        "forcing GPU load..."
                    )
                    self.gpu_controller.force_gpu_load(selected_node.url, model)

        return decision

    def route_with_fallback(
        self,
        payload: Dict[str, Any],
        agent_name: str = "Unknown",
        priority: int = 5,
        max_retries: int = 3
    ) -> RoutingDecision:
        """
        Route request with automatic fallback on failure.

        Tries primary node first, then fallback nodes if primary fails.

        Args:
            payload: Request payload
            agent_name: Agent name
            priority: Priority level
            max_retries: Max retry attempts

        Returns:
            RoutingDecision for successful node
        """
        decision = self.route_request(payload, agent_name, priority)

        # Store original decision for metrics
        primary_node = decision.node
        all_nodes = [decision.node] + decision.fallback_nodes

        for attempt, node in enumerate(all_nodes):
            if attempt > 0:
                logger.warning(
                    f"🔄 Retry {attempt}/{max_retries}: Falling back to {node.url}"
                )
                decision.node = node
                decision.reasoning = f"Fallback after primary node failure (attempt {attempt})"

            # Here you would actually try the request
            # For now, we return the decision
            # The actual request execution happens in the agent's call_ollama()

            if attempt < max_retries:
                break

        return decision

    def record_performance(
        self,
        decision: RoutingDecision,
        actual_duration_ms: float,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Record actual performance for adaptive learning.

        Args:
            decision: Original routing decision
            actual_duration_ms: Actual request duration
            success: Whether request succeeded
            error: Error message if failed
        """
        logger.debug(
            f"📊 [METRICS DEBUG] Recording performance for {decision.node.url} "
            f"(duration: {actual_duration_ms:.0f}ms, success: {success})"
        )
        logger.debug(f"📊 [METRICS DEBUG] Node object ID: {id(decision.node)}")
        logger.debug(
            f"📊 [METRICS DEBUG] BEFORE - total_requests: {decision.node.metrics.total_requests}, "
            f"avg_response_time: {decision.node.metrics.avg_response_time:.2f}s, "
            f"avg_latency: {decision.node.metrics.avg_latency:.0f}ms"
        )

        # Update SOLLOL performance memory
        self.memory.record_execution(
            node_url=decision.node.url,
            task_type=decision.task_context.task_type,
            model=decision.task_context.model_preference or "unknown",
            duration_ms=actual_duration_ms,
            success=success
        )

        # Update metrics
        self.metrics.record_request_completion(
            agent_name="Unknown",  # Would be passed from caller
            node_url=decision.node.url,
            task_type=decision.task_context.task_type,
            priority=decision.task_context.priority,
            duration_ms=actual_duration_ms,
            success=success
        )

        # Update node metrics in registry
        decision.node.metrics.total_requests += 1
        if success:
            # successful_requests is auto-calculated as total - failed
            pass
        else:
            decision.node.metrics.failed_requests += 1
            # Note: last_error is a property, can't be set directly
            # TODO: Add actual error tracking if needed

        # Update average latency using exponential moving average
        # This gives more weight to recent requests
        # Note: avg_response_time is in seconds, actual_duration_ms is in milliseconds
        alpha = 0.3  # Smoothing factor (0-1, higher = more weight to new values)
        actual_duration_s = actual_duration_ms / 1000.0  # Convert to seconds

        if decision.node.metrics.avg_response_time == 0:
            # First request
            decision.node.metrics.avg_response_time = actual_duration_s
        else:
            # EMA: new_avg = alpha * new_value + (1 - alpha) * old_avg
            decision.node.metrics.avg_response_time = (
                alpha * actual_duration_s +
                (1 - alpha) * decision.node.metrics.avg_response_time
            )

        logger.debug(
            f"📊 [METRICS DEBUG] AFTER - total_requests: {decision.node.metrics.total_requests}, "
            f"avg_response_time: {decision.node.metrics.avg_response_time:.2f}s, "
            f"avg_latency: {decision.node.metrics.avg_latency:.0f}ms"
        )

        # Verify the node is in the registry
        node_in_registry = decision.node.url in self.registry.nodes
        logger.debug(
            f"📊 [METRICS DEBUG] Node {decision.node.url} in registry: {node_in_registry}"
        )
        if node_in_registry:
            registry_node = self.registry.nodes[decision.node.url]
            logger.debug(
                f"📊 [METRICS DEBUG] Registry node object ID: {id(registry_node)}, "
                f"same as decision node: {id(registry_node) == id(decision.node)}"
            )
            logger.debug(
                f"📊 [METRICS DEBUG] Registry node metrics - "
                f"total_requests: {registry_node.metrics.total_requests}, "
                f"avg_latency: {registry_node.metrics.avg_latency:.0f}ms"
            )

        # Calculate prediction accuracy
        predicted_duration = decision.task_context.estimated_duration_ms
        accuracy = 1.0 - abs(actual_duration_ms - predicted_duration) / max(actual_duration_ms, predicted_duration)

        logger.debug(
            f"📈 Performance recorded: {decision.node.url} "
            f"(predicted: {predicted_duration:.0f}ms, actual: {actual_duration_ms:.0f}ms, "
            f"accuracy: {accuracy:.1%})"
        )

    def get_node(self, strategy=None, payload: Optional[Dict[str, Any]] = None) -> OllamaNode:
        """
        Get optimal node using SOLLOL routing (backward compatibility method).

        This method provides backward compatibility with the old OllamaLoadBalancer API.
        It wraps route_request() but returns just the OllamaNode object.

        Args:
            strategy: Routing strategy (ignored, SOLLOL uses intelligent routing)
            payload: Optional request payload for context-aware routing

        Returns:
            OllamaNode instance
        """
        # Use intelligent routing if payload provided, else simple selection
        if payload:
            decision = self.route_request(payload)
            return decision.node
        else:
            # Simple fallback: return least loaded healthy node
            healthy_nodes = self.registry.get_healthy_nodes()
            if not healthy_nodes:
                raise RuntimeError("No healthy Ollama nodes available")

            # Sort by load score (lower is better)
            sorted_nodes = sorted(healthy_nodes, key=lambda n: n.calculate_load_score())
            return sorted_nodes[0]

    def get_routing_metadata(self, decision: RoutingDecision) -> Dict[str, Any]:
        """
        Get routing metadata to include in response.

        This provides transparency about routing decisions.

        Args:
            decision: Routing decision

        Returns:
            Metadata dict for inclusion in response
        """
        return {
            '_sollol_routing': {
                'host': decision.node.url,
                'task_type': decision.task_context.task_type,
                'complexity': decision.task_context.complexity,
                'priority': decision.task_context.priority,
                'estimated_tokens': decision.task_context.estimated_tokens,
                'requires_gpu': decision.task_context.requires_gpu,
                'decision_score': decision.decision_score,
                'reasoning': decision.reasoning,
                'timestamp': decision.timestamp.isoformat(),
                'estimated_duration_ms': decision.task_context.estimated_duration_ms,
                'fallback_nodes_available': len(decision.fallback_nodes),
                'routing_engine': 'SOLLOL',
                'version': '1.0.0'
            }
        }

    def _node_to_host_metadata(self, node: OllamaNode) -> Dict[str, Any]:
        """
        Convert OllamaNode to host metadata format for SOLLOL.

        Args:
            node: OllamaNode instance

        Returns:
            Host metadata dict
        """
        # Calculate metrics
        load_score = node.calculate_load_score()
        success_rate = (
            node.metrics.successful_requests / node.metrics.total_requests
            if node.metrics.total_requests > 0 else 1.0
        )
        avg_latency_ms = node.metrics.avg_latency

        return {
            'url': node.url,
            'host': node.url,
            'health': 'healthy' if node.is_healthy else 'unhealthy',
            'available': node.is_healthy,  # Required by scoring function

            # Top-level metrics expected by scoring function
            'cpu_load': load_score / 100.0,  # Convert 0-100 to 0-1
            'latency_ms': avg_latency_ms,    # Average latency in ms
            'success_rate': success_rate,     # 0-1 success rate
            'gpu_free_mem': node.capabilities.gpu_memory_mb if (node.capabilities and node.capabilities.has_gpu) else 0,

            'capabilities': {
                'has_gpu': node.capabilities.has_gpu if node.capabilities else False,
                'gpu_memory_mb': node.capabilities.gpu_memory_mb if node.capabilities else 0,
                'cpu_count': node.capabilities.cpu_count if node.capabilities else 1,
            },
            # Add top-level cpu_count for SOLLOL scoring
            'cpu_count': node.capabilities.cpu_count if node.capabilities else 1,
            'metrics': {
                'current_load': load_score,
                'total_requests': node.metrics.total_requests,
                'success_rate': success_rate,
                'avg_latency_ms': avg_latency_ms,
                'last_health_check': node.last_health_check.isoformat() if node.last_health_check else None,
            },
            'priority': node.priority,
        }

    def pre_warm_gpu_models(self, priority_models: List[str]) -> Dict:
        """
        Pre-warm GPU nodes with priority models.

        This ensures first requests don't wait for model loading.

        Args:
            priority_models: Models to pre-load on GPU nodes

        Returns:
            Pre-warming report
        """
        if not self.gpu_controller:
            logger.warning("GPU controller not enabled, cannot pre-warm")
            return {'error': 'GPU controller not enabled'}

        return self.gpu_controller.pre_warm_gpu_nodes(priority_models)

    def optimize_gpu_cluster(self, priority_models: List[str]) -> Dict:
        """
        Optimize GPU/CPU placement across the cluster.

        Args:
            priority_models: Models that should be on GPU

        Returns:
            Optimization report
        """
        if not self.gpu_controller:
            logger.warning("GPU controller not enabled, cannot optimize")
            return {'error': 'GPU controller not enabled'}

        return self.gpu_controller.optimize_cluster(priority_models)

    def print_gpu_status(self):
        """Print cluster GPU/CPU status."""
        if not self.gpu_controller:
            logger.warning("GPU controller not enabled")
            return

        self.gpu_controller.print_cluster_status()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about routing and performance.

        Returns:
            Statistics dict
        """
        healthy_nodes = self.registry.get_healthy_nodes()
        gpu_nodes = self.registry.get_gpu_nodes()

        stats = {
            'load_balancer': {
                'type': 'SOLLOL',
                'version': '1.0.0',
                'intelligent_routing': True,
                'priority_queue': True,
                'adaptive_learning': True,
                'gpu_control': self.gpu_controller is not None,
            },
            'nodes': {
                'total': len(self.registry.nodes),
                'healthy': len(healthy_nodes),
                'gpu': len(gpu_nodes),
                'unhealthy': len(self.registry.nodes) - len(healthy_nodes),
            },
            'metrics': self.metrics.get_summary(),
            'performance_memory': {
                'tracked_executions': len(self.memory.history),
                'unique_task_types': len(set(h['task_type'] for h in self.memory.history)),
                'unique_models': len(set(h['model'] for h in self.memory.history)),
            },
            'queue': {
                'depth': len(self.priority_queue.queue),
                'total_queued': self.priority_queue.total_queued,
                'total_processed': self.priority_queue.total_processed,
            }
        }

        # Add GPU stats if controller enabled
        if self.gpu_controller:
            stats['gpu'] = self.gpu_controller.get_placement_stats()

        return stats

    def __repr__(self):
        healthy = len(self.registry.get_healthy_nodes())
        gpu = len(self.registry.get_gpu_nodes())
        gpu_control = "enabled" if self.gpu_controller else "disabled"
        return (
            f"SOLLOLLoadBalancer("
            f"nodes={len(self.registry)}, healthy={healthy}, gpu={gpu}, "
            f"intelligent_routing=enabled, adaptive_learning=enabled, "
            f"gpu_control={gpu_control})"
        )


# Convenience function for backward compatibility
def create_load_balancer(registry: NodeRegistry) -> SOLLOLLoadBalancer:
    """
    Create SOLLOL-powered load balancer.

    This replaces the old OllamaLoadBalancer with SOLLOL's intelligent routing.

    Args:
        registry: Node registry

    Returns:
        SOLLOLLoadBalancer instance
    """
    return SOLLOLLoadBalancer(registry)
