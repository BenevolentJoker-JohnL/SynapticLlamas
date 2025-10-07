"""
SOLLOL CLI - One-command startup for performance-aware Ollama load balancing.
"""
import typer
from .gateway import start_api
from .cluster import start_ray, start_dask

app = typer.Typer(
    name="sollol",
    help="SOLLOL - Super Ollama Load Balancer with performance-aware routing"
)

@app.command()
def up(
    workers: int = typer.Option(2, help="Number of Ray worker actors"),
    dask_workers: int = typer.Option(2, help="Number of Dask workers for batch processing"),
    hosts: str = typer.Option("config/hosts.txt", help="Path to OLLOL hosts configuration file"),
    port: int = typer.Option(8000, help="Port for FastAPI gateway"),
    dask_scheduler: str = typer.Option(None, help="External Dask scheduler address (e.g., tcp://10.0.0.1:8786)"),
    autobatch: bool = typer.Option(True, help="Enable autonomous batch processing"),
    autobatch_interval: int = typer.Option(60, help="Seconds between autobatch cycles"),
    adaptive_metrics: bool = typer.Option(True, help="Enable adaptive metrics feedback loop"),
    adaptive_metrics_interval: int = typer.Option(30, help="Seconds between adaptive metrics updates"),
):
    """
    Start SOLLOL with Ray + Dask + FastAPI gateway.

    Examples:
        sollol up
        sollol up --workers 4 --dask-workers 4 --port 8000
        sollol up --dask-scheduler tcp://10.0.0.1:8786
        sollol up --no-adaptive-metrics  # Disable dynamic metrics
    """
    print(f"🚀 Starting SOLLOL")
    print(f"   Ray workers: {workers}")
    print(f"   Dask workers: {dask_workers}")
    print(f"   API port: {port}")
    print(f"   Hosts file: {hosts}")
    if dask_scheduler:
        print(f"   Dask scheduler: {dask_scheduler}")
    print()

    # Initialize Ray cluster with Ollama workers
    ray_actors = start_ray(workers=workers, hosts_file=hosts)

    if not ray_actors:
        print("❌ Failed to initialize Ray workers. Exiting.")
        return

    # Initialize Dask cluster
    dask_client = start_dask(workers=dask_workers, scheduler_address=dask_scheduler)

    # Start FastAPI gateway (blocking call)
    start_api(
        ray_actors,
        dask_client,
        port=port,
        enable_autobatch=autobatch,
        autobatch_interval=autobatch_interval,
        enable_adaptive_metrics=adaptive_metrics,
        adaptive_metrics_interval=adaptive_metrics_interval
    )

@app.command()
def down():
    """
    Stop SOLLOL service.

    Note: For MVP, manually kill Ray/Dask processes:
        pkill -f "ray::"
        pkill -f "dask"
    """
    print("🛑 SOLLOL shutdown")
    print("   To stop Ray: pkill -f 'ray::'")
    print("   To stop Dask: pkill -f 'dask'")

@app.command()
def status():
    """
    Check SOLLOL service status.
    """
    print("📊 SOLLOL Status")
    print("   Gateway: http://localhost:8000/api/health")
    print("   Metrics: http://localhost:9090/metrics")
    print("   Stats: http://localhost:8000/api/stats")

if __name__ == "__main__":
    app()