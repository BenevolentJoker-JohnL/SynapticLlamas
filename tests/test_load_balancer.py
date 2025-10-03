"""Tests for load balancer functionality."""
import pytest
from unittest.mock import Mock, MagicMock
from load_balancer import OllamaLoadBalancer, RoutingStrategy
from node_registry import NodeRegistry
from ollama_node import OllamaNode


@pytest.fixture
def mock_registry():
    """Create a mock NodeRegistry."""
    registry = Mock(spec=NodeRegistry)
    registry.nodes = {}
    return registry


@pytest.fixture
def create_mock_node():
    """Factory for creating mock OllamaNode instances."""
    def _create_node(url, has_gpu=False, load=0, priority=1):
        node = Mock(spec=OllamaNode)
        node.url = url
        node.priority = priority
        node.capabilities = Mock()
        node.capabilities.has_gpu = has_gpu
        node.metrics = Mock()
        node.metrics.total_requests = load
        node.metrics.load_score = load
        node.calculate_load_score = Mock(return_value=load)
        return node
    return _create_node


class TestRoutingStrategies:
    """Test different routing strategies."""

    def test_least_loaded_strategy(self, mock_registry, create_mock_node):
        """Test LEAST_LOADED strategy selects node with lowest load."""
        node1 = create_mock_node("http://node1:11434", load=10)
        node2 = create_mock_node("http://node2:11434", load=5)
        node3 = create_mock_node("http://node3:11434", load=15)

        mock_registry.get_healthy_nodes.return_value = [node1, node2, node3]

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.LEAST_LOADED)
        selected = balancer.get_node()

        assert selected == node2

    def test_round_robin_strategy(self, mock_registry, create_mock_node):
        """Test ROUND_ROBIN strategy rotates through nodes."""
        node1 = create_mock_node("http://node1:11434")
        node2 = create_mock_node("http://node2:11434")
        node3 = create_mock_node("http://node3:11434")

        nodes = [node1, node2, node3]
        mock_registry.get_healthy_nodes.return_value = nodes

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.ROUND_ROBIN)

        # Should cycle through nodes
        assert balancer.get_node() == node1
        assert balancer.get_node() == node2
        assert balancer.get_node() == node3
        assert balancer.get_node() == node1

    def test_priority_strategy(self, mock_registry, create_mock_node):
        """Test PRIORITY strategy selects highest priority node."""
        node1 = create_mock_node("http://node1:11434", priority=1)
        node2 = create_mock_node("http://node2:11434", priority=5)
        node3 = create_mock_node("http://node3:11434", priority=3)

        mock_registry.get_healthy_nodes.return_value = [node1, node2, node3]

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.PRIORITY)
        selected = balancer.get_node()

        assert selected == node2

    def test_gpu_first_strategy(self, mock_registry, create_mock_node):
        """Test GPU_FIRST strategy prefers GPU nodes."""
        cpu_node = create_mock_node("http://cpu:11434", has_gpu=False, load=5)
        gpu_node = create_mock_node("http://gpu:11434", has_gpu=True, load=10)

        mock_registry.get_healthy_nodes.return_value = [cpu_node, gpu_node]

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.GPU_FIRST)
        selected = balancer.get_node()

        assert selected == gpu_node

    def test_gpu_first_fallback_to_cpu(self, mock_registry, create_mock_node):
        """Test GPU_FIRST falls back to CPU when no GPU available."""
        cpu_node1 = create_mock_node("http://cpu1:11434", has_gpu=False, load=5)
        cpu_node2 = create_mock_node("http://cpu2:11434", has_gpu=False, load=10)

        mock_registry.get_healthy_nodes.return_value = [cpu_node1, cpu_node2]

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.GPU_FIRST)
        selected = balancer.get_node()

        assert selected == cpu_node1  # Least loaded CPU node

    def test_random_strategy(self, mock_registry, create_mock_node):
        """Test RANDOM strategy returns a valid node."""
        node1 = create_mock_node("http://node1:11434")
        node2 = create_mock_node("http://node2:11434")

        nodes = [node1, node2]
        mock_registry.get_healthy_nodes.return_value = nodes

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.RANDOM)
        selected = balancer.get_node()

        assert selected in nodes


class TestGetMultipleNodes:
    """Test getting multiple nodes for parallel execution."""

    def test_get_multiple_nodes_least_loaded(self, mock_registry, create_mock_node):
        """Test getting multiple nodes with LEAST_LOADED strategy."""
        node1 = create_mock_node("http://node1:11434", load=10)
        node2 = create_mock_node("http://node2:11434", load=5)
        node3 = create_mock_node("http://node3:11434", load=15)

        mock_registry.get_healthy_nodes.return_value = [node1, node2, node3]

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.LEAST_LOADED)
        selected = balancer.get_nodes(2)

        assert len(selected) == 2
        assert node2 in selected  # Lowest load
        assert node1 in selected  # Second lowest load

    def test_get_more_nodes_than_available(self, mock_registry, create_mock_node):
        """Test requesting more nodes than available returns all nodes."""
        node1 = create_mock_node("http://node1:11434")
        node2 = create_mock_node("http://node2:11434")

        nodes = [node1, node2]
        mock_registry.get_healthy_nodes.return_value = nodes

        balancer = OllamaLoadBalancer(mock_registry)
        selected = balancer.get_nodes(5)

        assert len(selected) == 2
        assert set(selected) == set(nodes)

    def test_get_nodes_require_gpu(self, mock_registry, create_mock_node):
        """Test getting only GPU nodes."""
        cpu_node = create_mock_node("http://cpu:11434", has_gpu=False)
        gpu_node1 = create_mock_node("http://gpu1:11434", has_gpu=True)
        gpu_node2 = create_mock_node("http://gpu2:11434", has_gpu=True)

        mock_registry.get_gpu_nodes.return_value = [gpu_node1, gpu_node2]

        balancer = OllamaLoadBalancer(mock_registry)
        selected = balancer.get_nodes(2, require_gpu=True)

        assert len(selected) == 2
        assert cpu_node not in selected


class TestNoAvailableNodes:
    """Test behavior when no nodes are available."""

    def test_get_node_returns_none_when_no_nodes(self, mock_registry):
        """Test get_node returns None when no nodes available."""
        mock_registry.get_healthy_nodes.return_value = []

        balancer = OllamaLoadBalancer(mock_registry)
        selected = balancer.get_node()

        assert selected is None

    def test_get_nodes_returns_empty_list_when_no_nodes(self, mock_registry):
        """Test get_nodes returns empty list when no nodes available."""
        mock_registry.get_healthy_nodes.return_value = []

        balancer = OllamaLoadBalancer(mock_registry)
        selected = balancer.get_nodes(3)

        assert selected == []


class TestStrategyOverride:
    """Test strategy override functionality."""

    def test_override_default_strategy(self, mock_registry, create_mock_node):
        """Test overriding default strategy per request."""
        node1 = create_mock_node("http://node1:11434", priority=1)
        node2 = create_mock_node("http://node2:11434", priority=5)

        mock_registry.get_healthy_nodes.return_value = [node1, node2]

        # Default is LEAST_LOADED
        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.LEAST_LOADED)

        # Override with PRIORITY
        selected = balancer.get_node(strategy=RoutingStrategy.PRIORITY)

        assert selected == node2


class TestLoadBalancerStats:
    """Test load balancer statistics."""

    def test_get_stats(self, mock_registry, create_mock_node):
        """Test getting load balancer statistics."""
        node1 = create_mock_node("http://node1:11434")
        node1.metrics.total_requests = 100
        node1.metrics.failed_requests = 5
        node1.to_dict.return_value = {"url": "http://node1:11434"}

        node2 = create_mock_node("http://node2:11434")
        node2.metrics.total_requests = 50
        node2.metrics.failed_requests = 2
        node2.to_dict.return_value = {"url": "http://node2:11434"}

        mock_registry.nodes = {"node1": node1, "node2": node2}
        mock_registry.get_healthy_nodes.return_value = [node1, node2]
        mock_registry.get_gpu_nodes.return_value = []
        mock_registry.__len__ = Mock(return_value=2)

        balancer = OllamaLoadBalancer(mock_registry, RoutingStrategy.LEAST_LOADED)
        stats = balancer.get_stats()

        assert stats["total_nodes"] == 2
        assert stats["healthy_nodes"] == 2
        assert stats["gpu_nodes"] == 0
        assert stats["total_requests"] == 150
        assert stats["total_failures"] == 7
        assert stats["failure_rate"] == 7/150
        assert stats["strategy"] == "least_loaded"
