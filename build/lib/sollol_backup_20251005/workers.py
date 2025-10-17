"""
Ray actor wrapper for OLLOL (Ollama) requests with performance tracking.
"""
import ray
import httpx
import time
from sollol.metrics import record_host_request

@ray.remote
class OllamaWorker:
    """
    Ray actor that routes requests to OLLOL hosts.
    Host selection is determined dynamically by the calling code.
    """

    async def chat(self, payload: dict, host: str):
        """
        Send chat completion request to specified OLLOL host.

        Args:
            payload: Chat request payload (model, messages, etc.)
            host: OLLOL host address (e.g., "10.0.0.2:11434")

        Returns:
            Dict containing chat response or error
        """
        start_time = time.time()
        success = False

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(f"http://{host}/api/chat", json=payload)
                resp.raise_for_status()
                success = True
                return resp.json()
        except httpx.RequestError as e:
            return {"error": f"Request to {host} failed: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}
        finally:
            latency_ms = (time.time() - start_time) * 1000
            record_host_request(host, latency_ms, success)

    async def embed(self, text: str, host: str, model: str = "nomic-embed-text"):
        """
        Send embedding request to specified OLLOL host.

        Args:
            text: Text to embed
            host: OLLOL host address
            model: Embedding model to use

        Returns:
            Dict containing embedding response or error
        """
        start_time = time.time()
        success = False

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"http://{host}/api/embeddings",
                    json={"model": model, "prompt": text}
                )
                resp.raise_for_status()
                success = True
                return resp.json()
        except httpx.RequestError as e:
            return {"error": f"Request to {host} failed: {e}"}
        except Exception as e:
            return {"error": f"Unexpected error: {e}"}
        finally:
            latency_ms = (time.time() - start_time) * 1000
            record_host_request(host, latency_ms, success)
