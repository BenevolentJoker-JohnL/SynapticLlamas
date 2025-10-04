"""
Hybrid Router: Intelligent Selection Between Ollama and llama.cpp

Routes requests to either:
- Ollama nodes (for small/medium models that fit on single GPU)
- llama.cpp distributed cluster (for large models requiring multiple nodes)

This enables seamless support for models of ANY size while maintaining
Ollama's simple API.
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .pool import OllamaPool
from .llama_cpp_rpc import (
    LlamaCppDistributedCluster,
    LlamaCppNode,
    resolve_model_path
)

logger = logging.getLogger(__name__)


@dataclass
class ModelProfile:
    """Profile of a model's resource requirements."""
    name: str
    parameter_count: int  # Billion parameters
    estimated_memory_gb: float
    requires_distributed: bool
    num_layers: int = 0


# Model profiles for routing decisions
MODEL_PROFILES = {
    # Small models (fit on single GPU)
    "llama3.2": ModelProfile("llama3.2", 3, 2.5, False, 32),
    "llama3.2:3b": ModelProfile("llama3.2:3b", 3, 2.5, False, 32),
    "phi": ModelProfile("phi", 3, 1.5, False, 32),
    "phi3": ModelProfile("phi3", 4, 2.0, False, 32),
    "gemma:7b": ModelProfile("gemma:7b", 7, 5.0, False, 28),
    "llama3:8b": ModelProfile("llama3:8b", 8, 6.0, False, 32),
    "llama3.1:8b": ModelProfile("llama3.1:8b", 8, 6.0, False, 32),
    "mistral:7b": ModelProfile("mistral:7b", 7, 5.0, False, 32),
    "llama2:7b": ModelProfile("llama2:7b", 7, 5.0, False, 32),
    "llama2:13b": ModelProfile("llama2:13b", 13, 9.0, False, 40),

    # Medium models (might fit on large single GPU)
    "llama2:70b": ModelProfile("llama2:70b", 70, 40.0, True, 80),
    "llama3:70b": ModelProfile("llama3:70b", 70, 40.0, True, 80),
    "llama3.1:70b": ModelProfile("llama3.1:70b", 70, 40.0, True, 80),
    "mixtral:8x7b": ModelProfile("mixtral:8x7b", 47, 26.0, True, 32),
    "qwen2.5:72b": ModelProfile("qwen2.5:72b", 72, 42.0, True, 80),

    # Large models (REQUIRE distributed)
    "llama3.1:405b": ModelProfile("llama3.1:405b", 405, 230.0, True, 126),
    "mixtral:8x22b": ModelProfile("mixtral:8x22b", 141, 80.0, True, 56),
}


class HybridRouter:
    """
    Routes requests between Ollama and llama.cpp based on model requirements.

    Decision logic:
    1. Small models (<= 13B) → Ollama (single node)
    2. Medium models (14B-70B) → Ollama if available, else llama.cpp
    3. Large models (> 70B) → llama.cpp distributed cluster
    4. Unknown models → Estimate from name, fallback to Ollama
    """

    def __init__(
        self,
        ollama_pool: Optional[OllamaPool] = None,
        llamacpp_nodes: Optional[List[LlamaCppNode]] = None,
        enable_distributed: bool = True
    ):
        """
        Initialize hybrid router.

        Args:
            ollama_pool: OllamaPool for standard requests
            llamacpp_nodes: llama.cpp RPC nodes for distributed inference
            enable_distributed: Enable llama.cpp distributed routing
        """
        self.ollama_pool = ollama_pool
        self.llamacpp_clusters: Dict[str, LlamaCppDistributedCluster] = {}
        self.enable_distributed = enable_distributed and llamacpp_nodes is not None

        # Create distributed clusters if nodes available
        if self.enable_distributed and llamacpp_nodes:
            self._setup_distributed_clusters(llamacpp_nodes)

        logger.info(
            f"HybridRouter initialized: "
            f"Ollama={'enabled' if ollama_pool else 'disabled'}, "
            f"Distributed={'enabled' if self.enable_distributed else 'disabled'}"
        )

    def _setup_distributed_clusters(self, nodes: List[LlamaCppNode]):
        """Setup llama.cpp clusters for large models."""
        # Group nodes by model if specified, or create general cluster
        if all(node.model_path for node in nodes):
            # Nodes have specific models assigned
            clusters_by_model = {}
            for node in nodes:
                model = node.model_path.split('/')[-1].replace('.gguf', '')
                if model not in clusters_by_model:
                    clusters_by_model[model] = []
                clusters_by_model[model].append(node)

            for model, model_nodes in clusters_by_model.items():
                self.llamacpp_clusters[model] = LlamaCppDistributedCluster(
                    model_nodes,
                    model_name=model
                )
        else:
            # General cluster for all large models
            self.llamacpp_clusters['default'] = LlamaCppDistributedCluster(
                nodes,
                model_name='default'
            )

        logger.info(f"Created {len(self.llamacpp_clusters)} llama.cpp clusters")

    def should_use_distributed(self, model: str) -> bool:
        """
        Determine if model should use distributed inference.

        Args:
            model: Model name

        Returns:
            True if should use llama.cpp distributed
        """
        if not self.enable_distributed:
            return False

        # Get model profile
        profile = self._get_model_profile(model)

        # Decision rules
        if profile.parameter_count <= 13:
            # Small models: always use Ollama
            return False
        elif profile.parameter_count <= 70:
            # Medium models: prefer Ollama, use distributed if marked required
            return profile.requires_distributed
        else:
            # Large models: must use distributed
            return True

    def _get_model_profile(self, model: str) -> ModelProfile:
        """Get or estimate model profile."""
        # Normalize model name
        model_key = model.lower().strip()

        # Direct lookup
        if model_key in MODEL_PROFILES:
            return MODEL_PROFILES[model_key]

        # Try without tag
        base_model = model_key.split(':')[0]
        if base_model in MODEL_PROFILES:
            return MODEL_PROFILES[base_model]

        # Estimate from name
        return self._estimate_model_profile(model)

    def _estimate_model_profile(self, model: str) -> ModelProfile:
        """Estimate model requirements from name."""
        model_lower = model.lower()

        # Extract parameter count from name
        param_count = 8  # Default assumption

        # Common patterns
        if '405b' in model_lower:
            param_count = 405
        elif '70b' in model_lower:
            param_count = 70
        elif '34b' in model_lower:
            param_count = 34
        elif '13b' in model_lower:
            param_count = 13
        elif '8b' in model_lower:
            param_count = 8
        elif '7b' in model_lower:
            param_count = 7
        elif '3b' in model_lower:
            param_count = 3
        elif '1b' in model_lower:
            param_count = 1

        # Estimate memory (rough: ~600MB per billion parameters)
        estimated_memory = param_count * 0.6

        # Requires distributed if > 70B
        requires_distributed = param_count > 70

        logger.info(
            f"Estimated profile for '{model}': {param_count}B params, "
            f"~{estimated_memory:.1f}GB, distributed={requires_distributed}"
        )

        return ModelProfile(
            name=model,
            parameter_count=param_count,
            estimated_memory_gb=estimated_memory,
            requires_distributed=requires_distributed,
            num_layers=max(32, param_count)  # Rough estimate
        )

    async def route_request(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Route request to appropriate backend.

        Args:
            model: Model name
            messages: Chat messages
            **kwargs: Additional parameters

        Returns:
            Response from either Ollama or llama.cpp
        """
        use_distributed = self.should_use_distributed(model)

        if use_distributed:
            # Route to llama.cpp distributed cluster
            logger.info(f"🔗 Routing '{model}' to llama.cpp distributed cluster")
            return await self._route_to_llamacpp(model, messages, **kwargs)
        else:
            # Route to Ollama
            logger.info(f"📡 Routing '{model}' to Ollama pool")
            return await self._route_to_ollama(model, messages, **kwargs)

    async def _route_to_ollama(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Route to Ollama pool."""
        if not self.ollama_pool:
            raise RuntimeError("Ollama pool not available")

        # Convert messages to prompt if needed
        if isinstance(messages, list) and len(messages) > 0:
            # Use pool's chat method
            priority = kwargs.pop('priority', 5)
            result = self.ollama_pool.chat(
                model=model,
                messages=messages,
                priority=priority,
                **kwargs
            )
            return result
        else:
            raise ValueError("Invalid messages format")

    async def _route_to_llamacpp(
        self,
        model: str,
        messages: List[Dict[str, str]],
        **kwargs
    ) -> Dict[str, Any]:
        """Route to llama.cpp distributed cluster."""
        if not self.llamacpp_clusters:
            raise RuntimeError("No llama.cpp clusters available")

        # Get appropriate cluster
        cluster = self._get_cluster_for_model(model)

        # Convert messages to prompt (llama.cpp format)
        prompt = self._messages_to_prompt(messages)

        # Generate using distributed cluster
        result = await cluster.generate(prompt, kwargs)

        # Convert to Ollama-style response
        return self._convert_to_ollama_format(result)

    def _get_cluster_for_model(self, model: str) -> LlamaCppDistributedCluster:
        """Get appropriate cluster for model."""
        # Try model-specific cluster
        model_key = model.replace(':', '-')
        if model_key in self.llamacpp_clusters:
            return self.llamacpp_clusters[model_key]

        # Use default cluster
        if 'default' in self.llamacpp_clusters:
            return self.llamacpp_clusters['default']

        # Use any available cluster
        return next(iter(self.llamacpp_clusters.values()))

    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert Ollama messages to llama.cpp prompt format."""
        prompt_parts = []

        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')

            if role == 'system':
                prompt_parts.append(f"System: {content}")
            elif role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")

        prompt_parts.append("Assistant:")  # Prompt for response
        return "\n\n".join(prompt_parts)

    def _convert_to_ollama_format(self, llamacpp_result: Dict) -> Dict[str, Any]:
        """Convert llama.cpp response to Ollama format."""
        # Extract generated text
        content = llamacpp_result.get('content', '')

        # Build Ollama-style response
        return {
            'model': llamacpp_result.get('_distributed', {}).get('cluster', 'unknown'),
            'message': {
                'role': 'assistant',
                'content': content
            },
            'done': True,
            '_routing': {
                'backend': 'llama.cpp-distributed',
                'cluster_info': llamacpp_result.get('_distributed', {})
            }
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get routing statistics."""
        stats = {
            'ollama_enabled': self.ollama_pool is not None,
            'distributed_enabled': self.enable_distributed,
            'llamacpp_clusters': len(self.llamacpp_clusters)
        }

        if self.ollama_pool:
            stats['ollama_stats'] = self.ollama_pool.get_stats()

        return stats
