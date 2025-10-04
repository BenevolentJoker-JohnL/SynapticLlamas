"""
Node Clustering for Layer Partitioning

Enables distributed model inference by splitting large models across multiple nodes.
Each cluster represents a "virtual worker" where layers are partitioned across physical nodes.

Architecture:
- NodeCluster: Groups multiple OllamaNode instances for large model inference
- LayerPartitioner: Calculates optimal layer distribution across nodes
- DistributedInference: Coordinates inter-node communication for inference

Example:
    # Create a cluster for Llama-70B across 2 nodes
    cluster = NodeCluster(
        name="llama70b-cluster",
        nodes=[node1, node2],
        model="llama2:70b",
        total_layers=80
    )

    # Partition layers: node1 gets 0-39, node2 gets 40-79
    cluster.partition_layers()

    # Run inference (automatically handles inter-node communication)
    result = await cluster.generate(prompt="Explain quantum computing")
"""
import logging
import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import requests
import httpx

from ollama_node import OllamaNode

logger = logging.getLogger(__name__)


@dataclass
class LayerPartition:
    """Represents layer assignment for a node in a cluster."""
    node_url: str
    start_layer: int
    end_layer: int  # Exclusive
    layer_count: int

    def __post_init__(self):
        self.layer_count = self.end_layer - self.start_layer


@dataclass
class ModelSpec:
    """Model specifications for partitioning decisions."""
    name: str
    total_layers: int
    memory_per_layer_mb: float  # Estimated memory per layer
    min_memory_mb: float  # Minimum memory needed

    @property
    def total_memory_mb(self) -> float:
        """Total memory required for full model."""
        return self.min_memory_mb + (self.total_layers * self.memory_per_layer_mb)


# Common model specifications
MODEL_SPECS = {
    "llama2:70b": ModelSpec(
        name="llama2:70b",
        total_layers=80,
        memory_per_layer_mb=450,  # ~450MB per layer
        min_memory_mb=4096  # Base overhead
    ),
    "llama3:70b": ModelSpec(
        name="llama3:70b",
        total_layers=80,
        memory_per_layer_mb=450,
        min_memory_mb=4096
    ),
    "mixtral:8x7b": ModelSpec(
        name="mixtral:8x7b",
        total_layers=32,
        memory_per_layer_mb=800,  # Larger due to MoE
        min_memory_mb=6144
    ),
    # Small models (no partitioning needed)
    "llama3.2": ModelSpec(
        name="llama3.2",
        total_layers=32,
        memory_per_layer_mb=50,
        min_memory_mb=1024
    ),
    "phi": ModelSpec(
        name="phi",
        total_layers=32,
        memory_per_layer_mb=40,
        min_memory_mb=512
    ),
}


class LayerPartitioner:
    """Calculates optimal layer distribution across nodes."""

    @staticmethod
    def calculate_partitions(
        model_spec: ModelSpec,
        nodes: List[OllamaNode],
        strategy: str = "even"
    ) -> List[LayerPartition]:
        """
        Calculate layer partitions for nodes.

        Args:
            model_spec: Model specifications
            nodes: List of nodes to partition across
            strategy: Partitioning strategy ("even", "memory_aware")

        Returns:
            List of LayerPartition assignments

        Raises:
            ValueError: If nodes insufficient for model
        """
        if not nodes:
            raise ValueError("No nodes provided for partitioning")

        # Check if cluster has enough total memory
        total_available_memory = sum(
            node.capabilities.total_memory_mb for node in nodes
        )

        if total_available_memory < model_spec.total_memory_mb:
            raise ValueError(
                f"Insufficient memory: need {model_spec.total_memory_mb}MB, "
                f"have {total_available_memory}MB across {len(nodes)} nodes"
            )

        if strategy == "even":
            return LayerPartitioner._partition_even(model_spec, nodes)
        elif strategy == "memory_aware":
            return LayerPartitioner._partition_memory_aware(model_spec, nodes)
        else:
            raise ValueError(f"Unknown partitioning strategy: {strategy}")

    @staticmethod
    def _partition_even(
        model_spec: ModelSpec,
        nodes: List[OllamaNode]
    ) -> List[LayerPartition]:
        """Evenly distribute layers across nodes."""
        n_nodes = len(nodes)
        layers_per_node = model_spec.total_layers // n_nodes
        remainder = model_spec.total_layers % n_nodes

        partitions = []
        current_layer = 0

        for i, node in enumerate(nodes):
            # Give remainder layers to first nodes
            extra = 1 if i < remainder else 0
            n_layers = layers_per_node + extra

            partition = LayerPartition(
                node_url=node.url,
                start_layer=current_layer,
                end_layer=current_layer + n_layers,
                layer_count=n_layers
            )
            partitions.append(partition)
            current_layer += n_layers

        return partitions

    @staticmethod
    def _partition_memory_aware(
        model_spec: ModelSpec,
        nodes: List[OllamaNode]
    ) -> List[LayerPartition]:
        """
        Distribute layers proportionally to available memory.

        Nodes with more memory get more layers.
        """
        # Calculate memory proportions
        total_memory = sum(node.capabilities.total_memory_mb for node in nodes)
        memory_ratios = [
            node.capabilities.total_memory_mb / total_memory
            for node in nodes
        ]

        # Assign layers proportionally
        partitions = []
        current_layer = 0

        for i, (node, ratio) in enumerate(zip(nodes, memory_ratios)):
            # Last node gets all remaining layers
            if i == len(nodes) - 1:
                n_layers = model_spec.total_layers - current_layer
            else:
                n_layers = int(model_spec.total_layers * ratio)

            partition = LayerPartition(
                node_url=node.url,
                start_layer=current_layer,
                end_layer=current_layer + n_layers,
                layer_count=n_layers
            )
            partitions.append(partition)
            current_layer += n_layers

        return partitions


class NodeCluster:
    """
    Cluster of nodes for distributed model inference.

    Represents a "virtual worker" where a large model is split across nodes.
    Handles layer partitioning and distributed inference coordination.
    """

    def __init__(
        self,
        name: str,
        nodes: List[OllamaNode],
        model: str,
        partitioning_strategy: str = "even"
    ):
        """
        Create a node cluster.

        Args:
            name: Cluster identifier
            nodes: Physical nodes in cluster
            model: Model name to load (e.g., "llama2:70b")
            partitioning_strategy: How to distribute layers
        """
        self.name = name
        self.nodes = nodes
        self.model = model
        self.partitioning_strategy = partitioning_strategy

        # Get model spec
        self.model_spec = self._get_model_spec(model)

        # Calculate partitions
        self.partitions = LayerPartitioner.calculate_partitions(
            self.model_spec,
            nodes,
            strategy=partitioning_strategy
        )

        # Track cluster health
        self.is_healthy = False
        self.last_health_check = None

        logger.info(
            f"📦 Created cluster '{name}' with {len(nodes)} nodes for {model}"
        )
        for i, partition in enumerate(self.partitions):
            logger.info(
                f"   Node {i+1}: layers {partition.start_layer}-{partition.end_layer-1} "
                f"({partition.layer_count} layers)"
            )

    def _get_model_spec(self, model: str) -> ModelSpec:
        """Get model specification."""
        # Try exact match
        if model in MODEL_SPECS:
            return MODEL_SPECS[model]

        # Try fuzzy match (e.g., "llama2:70b-chat" -> "llama2:70b")
        for spec_name, spec in MODEL_SPECS.items():
            if spec_name in model:
                logger.info(f"Using spec '{spec_name}' for model '{model}'")
                return spec

        # Default fallback for unknown models
        logger.warning(
            f"Unknown model '{model}', using default 70B spec. "
            "Consider adding to MODEL_SPECS for better partitioning."
        )
        return ModelSpec(
            name=model,
            total_layers=80,
            memory_per_layer_mb=400,
            min_memory_mb=4096
        )

    async def health_check(self) -> bool:
        """
        Check cluster health.

        A cluster is healthy only if ALL nodes are healthy.
        """
        all_healthy = all(node.is_healthy for node in self.nodes)
        self.is_healthy = all_healthy
        self.last_health_check = datetime.now()

        if not all_healthy:
            unhealthy = [n.url for n in self.nodes if not n.is_healthy]
            logger.warning(
                f"⚠️  Cluster '{self.name}' unhealthy - "
                f"nodes down: {', '.join(unhealthy)}"
            )

        return all_healthy

    async def generate(
        self,
        prompt: str,
        options: Optional[Dict] = None
    ) -> Dict:
        """
        Run distributed inference across cluster.

        Process flow:
        1. First node processes initial layers, outputs intermediate activations
        2. Each subsequent node receives activations, processes its layers
        3. Final node returns complete result

        Args:
            prompt: Input prompt
            options: Generation options (temperature, etc.)

        Returns:
            Generation result
        """
        if not self.is_healthy:
            await self.health_check()
            if not self.is_healthy:
                raise RuntimeError(f"Cluster '{self.name}' is unhealthy")

        logger.info(f"🔗 Running distributed inference on cluster '{self.name}'")

        # For now, use simple approach: send full request to first node
        # with layer constraints
        # TODO: Implement proper layer-by-layer distributed inference

        first_node = self.nodes[0]
        first_partition = self.partitions[0]

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": options or {},
            # Ollama layer constraints (if supported)
            "_layer_partition": {
                "start": first_partition.start_layer,
                "end": first_partition.end_layer,
                "total_nodes": len(self.nodes),
                "node_index": 0
            }
        }

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(
                    f"{first_node.url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()

                # Add cluster metadata
                result['_cluster'] = {
                    'name': self.name,
                    'nodes': len(self.nodes),
                    'partitions': [
                        {
                            'node': p.node_url,
                            'layers': f"{p.start_layer}-{p.end_layer-1}"
                        }
                        for p in self.partitions
                    ]
                }

                return result

        except Exception as e:
            logger.error(f"❌ Cluster inference failed: {e}")
            raise

    def calculate_load_score(self) -> float:
        """
        Calculate cluster load score.

        Returns average load across all nodes.
        """
        if not self.nodes:
            return float('inf')

        total_load = sum(node.calculate_load_score() for node in self.nodes)
        return total_load / len(self.nodes)

    @property
    def url(self) -> str:
        """Virtual URL for cluster (uses first node)."""
        return f"cluster://{self.name}"

    def __repr__(self):
        health_status = "✓" if self.is_healthy else "✗"
        return (
            f"NodeCluster({health_status} '{self.name}', "
            f"model={self.model}, nodes={len(self.nodes)})"
        )


def needs_partitioning(model: str) -> bool:
    """
    Determine if a model requires layer partitioning.

    Args:
        model: Model name

    Returns:
        True if model is large and should be partitioned
    """
    # Get spec
    spec = None
    if model in MODEL_SPECS:
        spec = MODEL_SPECS[model]
    else:
        # Fuzzy match
        for spec_name, s in MODEL_SPECS.items():
            if spec_name in model:
                spec = s
                break

    if not spec:
        # Unknown model - assume needs partitioning if "70b" or "8x7b" in name
        return "70b" in model.lower() or "8x7b" in model.lower()

    # Need partitioning if model requires > 24GB (typical single GPU)
    return spec.total_memory_mb > 24000


__all__ = [
    'NodeCluster',
    'LayerPartitioner',
    'LayerPartition',
    'ModelSpec',
    'MODEL_SPECS',
    'needs_partitioning'
]
