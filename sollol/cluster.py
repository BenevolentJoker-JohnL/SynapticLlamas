"""
Cluster initialization for Ray and Dask with host discovery and metrics tracking.
"""
import ray
import logging
from .workers import OllamaWorker
from dask.distributed import Client, LocalCluster
from sollol.memory import load_hosts_from_file, init_hosts_meta
from sollol.metrics import init_host_stats

def start_ray(workers: int = 1, hosts_file: str = "config/hosts.txt"):
    """
    Initialize Ray cluster with Ollama worker actors.

    Args:
        workers: Number of Ray actor workers to spawn
        hosts_file: Path to hosts configuration file

    Returns:
        List of Ray OllamaWorker actors
    """
    ray.init(ignore_reinit_error=True)

    # Load OLLOL hosts from configuration
    hosts = load_hosts_from_file(hosts_file)

    if not hosts:
        print(f"❌ No hosts found in '{hosts_file}'. Please configure OLLOL hosts.")
        print(f"   Example: echo '127.0.0.1:11434' > {hosts_file}")
        return []

    # Initialize host metadata and metrics tracking
    init_hosts_meta(hosts)
    init_host_stats(hosts)

    # Spawn Ray actors (no longer tied to specific hosts)
    # Actors will receive host dynamically per request based on routing
    actors = [OllamaWorker.remote() for _ in range(workers)]
    print(f"✅ Ray initialized with {len(actors)} Ollama workers")
    print(f"✅ Discovered {len(hosts)} OLLOL hosts: {', '.join(hosts)}")

    return actors

def start_dask(workers: int = 1, scheduler_address: str = None):
    """
    Initialize Dask distributed cluster.

    Args:
        workers: Number of Dask workers for local cluster
        scheduler_address: Optional external Dask scheduler address (e.g., "tcp://10.0.0.1:8786")

    Returns:
        Dask Client instance, or None if initialization fails
    """
    try:
        if scheduler_address:
            # Connect to existing Dask scheduler
            client = Client(scheduler_address, timeout='10s')
            print(f"✅ Dask connected to scheduler: {scheduler_address}")
            return client
        else:
            # Try to start local Dask cluster
            # Use threading mode to avoid multiprocessing issues
            cluster = LocalCluster(
                n_workers=workers,
                threads_per_worker=4,
                processes=False,  # Use threads to avoid spawn issues
                silence_logs=logging.WARNING,
            )
            client = Client(cluster)
            print(f"✅ Dask initialized with {workers} threaded workers")
            print(f"   Note: Using threads. For better performance, use external scheduler:")
            print(f"   dask scheduler && sollol up --dask-scheduler tcp://127.0.0.1:8786")
            return client

    except Exception as e:
        print(f"⚠️  Dask initialization failed: {e}")
        print(f"   SOLLOL will run without batch processing features")
        print(f"   To enable batch processing, start external Dask:")
        print(f"     dask scheduler")
        print(f"     sollol up --dask-scheduler tcp://127.0.0.1:8786")
        return None
