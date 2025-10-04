"""
llama.cpp Coordinator for Distributed Inference

Manages llama-server instances configured with --rpc flag to coordinate
distributed inference across multiple RPC backend nodes.

Architecture:
    Python Client → llama-server (coordinator) → RPC servers (workers)

The coordinator (llama-server) handles:
- Automatic layer slicing across RPC backends
- Inter-node communication via RPC protocol
- Standard HTTP API (Ollama-compatible)

We just manage starting the coordinator and providing the right RPC backend addresses.
"""

import asyncio
import subprocess
import logging
import httpx
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RPCBackend:
    """Configuration for an RPC backend node."""
    host: str
    port: int = 50052

    @property
    def address(self) -> str:
        return f"{self.host}:{self.port}"


class LlamaCppCoordinator:
    """
    Manages llama-server as coordinator for distributed inference.

    The coordinator automatically distributes model layers across RPC
    backends and handles all inter-node communication.

    Usage:
        coordinator = LlamaCppCoordinator(
            model_path="/path/to/model.gguf",
            rpc_backends=[
                RPCBackend("192.168.1.10", 50052),
                RPCBackend("192.168.1.11", 50052)
            ]
        )

        await coordinator.start()

        # Use standard HTTP API
        response = await coordinator.generate("Hello world")
    """

    def __init__(
        self,
        model_path: str,
        rpc_backends: List[RPCBackend],
        host: str = "127.0.0.1",
        port: int = 8080,
        n_gpu_layers: int = 99,
        ctx_size: int = 8192
    ):
        """
        Initialize coordinator.

        Args:
            model_path: Path to .gguf model file
            rpc_backends: List of RPC backend nodes
            host: Host to bind llama-server to
            port: Port for llama-server HTTP API
            n_gpu_layers: Number of layers to attempt GPU offload
            ctx_size: Context window size
        """
        self.model_path = model_path
        self.rpc_backends = rpc_backends
        self.host = host
        self.port = port
        self.n_gpu_layers = n_gpu_layers
        self.ctx_size = ctx_size

        self.process: Optional[subprocess.Popen] = None
        self.http_client = httpx.AsyncClient(timeout=300.0)

    async def start(self):
        """
        Start llama-server coordinator with RPC backends.

        Command format:
            llama-server \\
              --model model.gguf \\
              --host 0.0.0.0 \\
              --port 8080 \\
              --rpc node1:50052,node2:50052,node3:50052 \\
              --gpu-layers 99 \\
              --ctx-size 8192
        """
        # Build RPC backend address list
        rpc_addresses = ",".join([backend.address for backend in self.rpc_backends])

        # Build llama-server command
        cmd = [
            "llama-server",
            "--model", self.model_path,
            "--host", self.host,
            "--port", str(self.port),
            "--rpc", rpc_addresses,
            "--gpu-layers", str(self.n_gpu_layers),
            "--ctx-size", str(self.ctx_size),
        ]

        logger.info(f"Starting llama-server coordinator: {' '.join(cmd)}")

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for server to be ready
            await self._wait_for_ready()

            logger.info(
                f"✅ llama-server coordinator started on {self.host}:{self.port} "
                f"with {len(self.rpc_backends)} RPC backends"
            )

        except Exception as e:
            logger.error(f"Failed to start llama-server: {e}")
            raise

    async def _wait_for_ready(self, timeout: float = 30.0):
        """Wait for llama-server to be ready."""
        start_time = asyncio.get_event_loop().time()

        while True:
            try:
                response = await self.http_client.get(
                    f"http://{self.host}:{self.port}/health"
                )
                if response.status_code == 200:
                    return
            except:
                pass

            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("llama-server did not start in time")

            await asyncio.sleep(0.5)

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate text using distributed inference.

        Args:
            prompt: Input text
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional generation parameters

        Returns:
            Response from llama-server
        """
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stream": False,
            **kwargs
        }

        response = await self.http_client.post(
            f"http://{self.host}:{self.port}/completion",
            json=payload
        )
        response.raise_for_status()

        return response.json()

    async def chat(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 512,
        temperature: float = 0.7,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Chat completion using distributed inference.

        Args:
            messages: List of chat messages
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            **kwargs: Additional generation parameters

        Returns:
            Response from llama-server
        """
        payload = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
            **kwargs
        }

        response = await self.http_client.post(
            f"http://{self.host}:{self.port}/v1/chat/completions",
            json=payload
        )
        response.raise_for_status()

        return response.json()

    async def stop(self):
        """Stop the llama-server coordinator."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

            logger.info("llama-server coordinator stopped")

        await self.http_client.aclose()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


async def start_rpc_backend(
    host: str = "0.0.0.0",
    port: int = 50052,
    mem_mb: int = 2048
) -> subprocess.Popen:
    """
    Start an RPC backend server on a node.

    This should be run on each worker node.

    Command:
        rpc-server --host 0.0.0.0 --port 50052 --mem 2048

    Args:
        host: Host to bind to
        port: Port for RPC server
        mem_mb: Memory limit in MB

    Returns:
        Process handle
    """
    cmd = [
        "rpc-server",
        "--host", host,
        "--port", str(port),
        "--mem", str(mem_mb)
    ]

    logger.info(f"Starting RPC backend: {' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give it a moment to start
    await asyncio.sleep(1)

    logger.info(f"✅ RPC backend started on {host}:{port}")

    return process
