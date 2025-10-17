"""
Autonomous batch processing pipeline for SOLLOL.
Continuously monitors for new documents and schedules embeddings.
"""
import asyncio
from datetime import datetime
from typing import Optional
from sollol.batch import run_batch_pipeline
from sollol.memory import fetch_new_docs

async def autobatch_loop(
    dask_client,
    interval_sec: int = 60,
    min_batch_size: int = 1,
    max_batch_size: int = 100
):
    """
    Autonomous batch processing loop.

    Continuously polls for new documents and submits them for processing via Dask.

    Args:
        dask_client: Dask distributed client
        interval_sec: Seconds to wait between polling cycles
        min_batch_size: Minimum number of docs to trigger a batch
        max_batch_size: Maximum docs to process in a single batch
    """
    print(f"🔄 Autobatch loop started (interval: {interval_sec}s)")

    while True:
        try:
            # Fetch new documents from queue/database
            docs = fetch_new_docs()

            if len(docs) >= min_batch_size:
                # Limit batch size
                batch = docs[:max_batch_size]

                # Submit to Dask for distributed processing
                futures = run_batch_pipeline(dask_client, batch)

                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"🚀 Submitted {len(batch)} documents for embedding"
                )

                # Optional: track futures if you want to monitor completion
                # for future in futures:
                #     result = await future.result()

            else:
                print(
                    f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                    f"💤 No new documents to embed (found {len(docs)})"
                )

        except Exception as e:
            print(
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"❌ Autobatch error: {e}"
            )

        await asyncio.sleep(interval_sec)

async def manual_batch_job(dask_client, docs: list):
    """
    Manually trigger a batch embedding job.

    Args:
        dask_client: Dask distributed client
        docs: List of documents to embed

    Returns:
        List of Dask futures
    """
    print(f"🔧 Manual batch job triggered for {len(docs)} documents")
    return run_batch_pipeline(dask_client, docs)
