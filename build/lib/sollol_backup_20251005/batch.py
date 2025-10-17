"""
Dask batch processing with performance-aware routing to OLLOL nodes.
"""
from dask import delayed
import asyncio
import httpx
import time
from sollol.memory import get_best_host
from sollol.metrics import record_host_request

def remote_embed(doc: str, model: str = "nomic-embed-text") -> dict:
    """
    Embed a single document using the best available OLLOL host.

    Args:
        doc: Text document to embed
        model: Ollama embedding model to use

    Returns:
        Dict containing embedding result
    """
    host = get_best_host(task_type="embedding")

    if not host:
        return {"error": "No available OLLOL hosts", "doc": doc}

    async def _embed():
        start_time = time.time()
        success = False

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"http://{host}/api/embeddings",
                    json={"model": model, "prompt": doc}
                )
                resp.raise_for_status()
                success = True
                return resp.json()
        except Exception as e:
            return {"error": str(e), "doc": doc, "host": host}
        finally:
            latency_ms = (time.time() - start_time) * 1000
            record_host_request(host, latency_ms, success)

    return asyncio.run(_embed())

def remote_chat(payload: dict) -> dict:
    """
    Send a chat request to the best available OLLOL host.

    Args:
        payload: Chat payload (model, messages, etc.)

    Returns:
        Dict containing chat response
    """
    host = get_best_host(task_type="chat")

    if not host:
        return {"error": "No available OLLOL hosts"}

    async def _chat():
        start_time = time.time()
        success = False

        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"http://{host}/api/chat",
                    json=payload
                )
                resp.raise_for_status()
                success = True
                return resp.json()
        except Exception as e:
            return {"error": str(e), "host": host}
        finally:
            latency_ms = (time.time() - start_time) * 1000
            record_host_request(host, latency_ms, success)

    return asyncio.run(_chat())

def embed_documents(docs: list, model: str = "nomic-embed-text") -> list:
    """
    Create Dask task graph for embedding multiple documents.

    Each document is routed to the optimal OLLOL host based on performance metrics.

    Args:
        docs: List of text documents to embed
        model: Ollama embedding model to use

    Returns:
        List of Dask delayed tasks
    """
    tasks = [delayed(remote_embed)(doc, model) for doc in docs]
    return tasks

def run_batch_pipeline(dask_client, docs: list, model: str = "nomic-embed-text"):
    """
    Execute batch embedding pipeline using Dask.

    Args:
        dask_client: Dask distributed client
        docs: List of documents to embed
        model: Ollama model to use

    Returns:
        List of Dask futures
    """
    tasks = embed_documents(docs, model)
    futures = dask_client.compute(tasks, sync=False)
    return futures