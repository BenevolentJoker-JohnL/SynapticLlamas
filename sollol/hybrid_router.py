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
from .llama_cpp_coordinator import LlamaCppCoordinator, RPCBackend
from .ollama_gguf_resolver import OllamaGGUFResolver

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
        rpc_backends: Optional[List[Dict[str, Any]]] = None,
        coordinator_host: str = "127.0.0.1",
        coordinator_port: int = 8080,
        enable_distributed: bool = True,
        auto_discover_rpc: bool = True
    ):
        """
        Initialize hybrid router with automatic GGUF resolution from Ollama.

        Args:
            ollama_pool: OllamaPool for standard requests
            rpc_backends: List of RPC backend configs [{"host": "ip", "port": 50052}]
                         If None and auto_discover_rpc=True, will auto-discover
            coordinator_host: Host for llama-server coordinator
            coordinator_port: Port for llama-server coordinator
            enable_distributed: Enable llama.cpp distributed routing
            auto_discover_rpc: Auto-discover RPC backends if none provided
        """
        self.ollama_pool = ollama_pool

        # Auto-discover RPC backends if none provided
        if rpc_backends is None and enable_distributed and auto_discover_rpc:
            logger.info("🔍 Auto-discovering RPC backends...")
            from .rpc_discovery import auto_discover_rpc_backends
            discovered = auto_discover_rpc_backends()
            if discovered:
                rpc_backends = discovered
                logger.info(f"✅ Auto-discovered {len(discovered)} RPC backends")
            else:
                logger.info("ℹ️  No RPC backends found via auto-discovery")

        self.enable_distributed = enable_distributed and rpc_backends is not None

        # Store RPC backend configs for on-demand coordinator creation
        self.rpc_backends = rpc_backends
        self.coordinator_host = coordinator_host
        self.coordinator_port = coordinator_port

        # Coordinator created on-demand when first large model request arrives
        self.coordinator: Optional[LlamaCppCoordinator] = None
        self.coordinator_model: Optional[str] = None  # Track which model is loaded

        # GGUF resolver for extracting models from Ollama storage
        self.gguf_resolver = OllamaGGUFResolver()

        # Log initialization status
        rpc_info = ""
        if self.enable_distributed:
            rpc_info = f", RPC backends={len(self.rpc_backends)}"

        logger.info(
            f"HybridRouter initialized: "
            f"Ollama={'enabled' if ollama_pool else 'disabled'}, "
            f"Distributed={'enabled' if self.enable_distributed else 'disabled'}"
            f"{rpc_info}"
        )

    async def _ensure_coordinator_for_model(self, model: str):
        """
        Ensure coordinator is started with the correct model.

        This method:
        1. Resolves GGUF path from Ollama storage (automatic!)
        2. Creates coordinator if not exists
        3. Restarts coordinator if different model requested
        4. Starts coordinator if not already running

        Args:
            model: Ollama model name (e.g., "llama3.1:405b")
        """
        # If coordinator exists and serving same model, we're done
        if self.coordinator and self.coordinator_model == model:
            return

        # Resolve GGUF path from Ollama storage
        logger.info(f"🔍 Resolving GGUF path for Ollama model: {model}")
        gguf_path = self.gguf_resolver.resolve(model)

        if not gguf_path:
            raise FileNotFoundError(
                f"Could not find GGUF for '{model}' in Ollama storage. "
                f"Please ensure model is pulled: ollama pull {model}"
            )

        logger.info(f"✅ Found GGUF: {gguf_path}")

        # Stop existing coordinator if serving different model
        if self.coordinator and self.coordinator_model != model:
            logger.info(f"Stopping coordinator (switching from {self.coordinator_model} to {model})")
            await self.coordinator.stop()
            self.coordinator = None

        # Create coordinator if needed
        if not self.coordinator:
            # Convert dict configs to RPCBackend objects
            backends = [
                RPCBackend(
                    host=backend['host'],
                    port=backend.get('port', 50052)
                )
                for backend in self.rpc_backends
            ]

            # Create coordinator
            self.coordinator = LlamaCppCoordinator(
                model_path=gguf_path,
                rpc_backends=backends,
                host=self.coordinator_host,
                port=self.coordinator_port
            )

            # Start coordinator
            logger.info(f"🚀 Starting llama.cpp coordinator for {model}...")
            await self.coordinator.start()

            # Track which model is loaded
            self.coordinator_model = model

            logger.info(
                f"✅ Coordinator started with {len(backends)} RPC backends "
                f"on {self.coordinator_host}:{self.coordinator_port}"
            )

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
        """
        Route to llama.cpp distributed coordinator.

        This method automatically:
        1. Resolves the GGUF from Ollama's blob storage
        2. Starts the coordinator with the correct model
        3. Makes the inference request
        """
        # Ensure coordinator is started with correct model (auto-resolves GGUF!)
        await self._ensure_coordinator_for_model(model)

        # Use the coordinator's chat method (which uses /v1/chat/completions endpoint)
        result = await self.coordinator.chat(
            messages=messages,
            max_tokens=kwargs.get('max_tokens', 512),
            temperature=kwargs.get('temperature', 0.7)
        )

        # Convert to Ollama-style response
        return self._convert_llamacpp_to_ollama(result, model)

    def _convert_llamacpp_to_ollama(
        self,
        llamacpp_result: Dict,
        model: str
    ) -> Dict[str, Any]:
        """Convert llama.cpp response to Ollama format."""
        # llama.cpp /v1/chat/completions returns OpenAI-compatible format
        # Extract the message content
        choices = llamacpp_result.get('choices', [])
        if choices:
            message = choices[0].get('message', {})
            content = message.get('content', '')
        else:
            content = ''

        # Build Ollama-style response
        return {
            'model': model,
            'message': {
                'role': 'assistant',
                'content': content
            },
            'done': True,
            '_routing': {
                'backend': 'llama.cpp-distributed',
                'coordinator': f"{self.coordinator.host}:{self.coordinator.port}",
                'rpc_backends': len(self.coordinator.rpc_backends)
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
