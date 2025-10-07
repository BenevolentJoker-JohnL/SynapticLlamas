
import asyncio
import time
import aiohttp
import json
from itertools import cycle
from starlette.requests import Request
from starlette.responses import Response, StreamingResponse, JSONResponse
from typing import Dict, List

from ray import serve

# --- Configuration ---
HEALTH_CHECK_INTERVAL_S = 10
BENCHMARK_TIMEOUT_S = 20 # Timeout for the benchmark generation task
# ---

@serve.deployment
class OllamaProxy:
    def __init__(self, workers: List[str]):
        if not workers:
            raise ValueError("Cannot start OllamaProxy with an empty list of workers.")
        self._workers = workers
        self._worker_scores: Dict[str, float] = {w: float('inf') for w in self._workers}
        self._client_session = aiohttp.ClientSession()
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        print(f"OllamaProxy started with workers: {self._workers}")
        print(f"Benchmark-based health checks running every {HEALTH_CHECK_INTERVAL_S} seconds.")

    async def _health_check_loop(self):
        """Periodically benchmarks each worker to calculate a true performance score."""
        # This model should be available on all workers for an accurate benchmark.
        # In a future version, this could be made configurable.
        benchmark_payload = {
            "model": "llama3", # A small, common model is best
            "prompt": "Hello",
            "stream": False,
            "options": {"num_predict": 5} # Generate a few tokens
        }

        while True:
            for worker in self._workers:
                new_score = float('inf')
                try:
                    async with self._client_session.post(
                        f"{worker}/api/generate", 
                        json=benchmark_payload, 
                        timeout=BENCHMARK_TIMEOUT_S
                    ) as resp:
                        resp.raise_for_status()
                        data = await resp.json()
                        
                        # The score is the actual generation time from Ollama's response
                        if "total_duration" in data:
                            new_score = data["total_duration"] / 1e9  # Convert ns to seconds
                        else:
                            raise ValueError("'total_duration' not in benchmark response")

                    if self._worker_scores.get(worker, float('inf')) == float('inf'):
                        print(f"Worker {worker} is now HEALTHY (score: {new_score:.4f}s)")

                except Exception as e:
                    if self._worker_scores.get(worker, float('inf')) != float('inf'):
                        print(f"Worker {worker} is now UNHEALTHY (reason: {type(e).__name__})")
                
                self._worker_scores[worker] = new_score

            await asyncio.sleep(HEALTH_CHECK_INTERVAL_S)

    def _get_workers_sorted_by_score(self) -> list[str]:
        sorted_workers = sorted(self._worker_scores.items(), key=lambda item: item[1])
        return [w for w, s in sorted_workers if s != float('inf')]

    async def _proxy_request(self, request: Request) -> Response:
        healthy_workers = self._get_workers_sorted_by_score()
        if not healthy_workers:
            return Response("All Ollama workers are unavailable.", status_code=503)
        headers = {k: v for k, v in request.headers.items() if k.lower() not in ('host', 'user-agent', 'accept-encoding')}
        for worker_url in healthy_workers:
            target_url = worker_url + request.url.path
            try:
                async with self._client_session.request(
                    method=request.method, url=target_url, data=request.stream(), headers=headers
                ) as ollama_resp:
                    ollama_resp.raise_for_status()
                    async def streamer():
                        async for chunk in ollama_resp.content.iter_any(): yield chunk
                    return StreamingResponse(streamer(), status_code=ollama_resp.status, media_type=ollama_resp.content_type)
            except aiohttp.ClientError as e:
                print(f"WARN: Proxy request to {worker_url} failed: {e}. Trying next.")
                self._worker_scores[worker_url] = float('inf')
                continue
        return Response("All healthy workers failed to respond.", status_code=503)

    async def _send_parallel_request(self, worker_url: str, payload: dict) -> dict:
        try:
            async with self._client_session.post(f"{worker_url}/api/generate", json=payload) as resp:
                resp.raise_for_status()
                return await resp.json()
        except Exception as e:
            self._worker_scores[worker_url] = float('inf')
            print(f"ERROR: Parallel request to {worker_url} failed: {e}")
            return {"error": str(e), "worker": worker_url}

    async def _parallel_generate(self, request: Request) -> Response:
        try:
            body = await request.json()
            model, prompts, stream = body.get("model"), body.get("prompts"), body.get("stream", False)
        except Exception:
            return Response("Invalid JSON body.", status_code=400)
        if not all([model, prompts]):
            return Response("Request must include 'model' and 'prompts'.", status_code=400)
        if stream:
            return Response("Streaming is not supported for /api/parallel/generate.", status_code=400)
        healthy_workers = self._get_workers_sorted_by_score()
        if not healthy_workers:
            return Response("All Ollama workers are unavailable.", status_code=503)
        worker_cycler = cycle(healthy_workers)
        tasks = [self._send_parallel_request(next(worker_cycler), {"model": model, "prompt": p, "stream": False}) for p in prompts]
        results = await asyncio.gather(*tasks)
        return JSONResponse(content=results)

    async def __call__(self, request: Request) -> Response:
        if request.url.path == "/api/parallel/generate":
            return await self._parallel_generate(request)
        return await self._proxy_request(request)

    async def __del__(self):
        if self._client_session: await self._client_session.close()
