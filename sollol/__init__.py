"""
SOLLOL - Super Ollama Load Balancer

Performance-aware load balancing for Ollama with Ray, Dask, and adaptive routing.

Example:
    ```python
    from sollol import SOLLOL, SOLLOLConfig

    # Configure SOLLOL for your application
    config = SOLLOLConfig(
        ray_workers=4,
        dask_workers=4,
        hosts=["10.0.0.2:11434", "10.0.0.3:11434"],
        autobatch_interval=30
    )

    # Initialize and start
    sollol = SOLLOL(config)
    sollol.start(blocking=False)  # Run in background

    # Your application code continues...
    # SOLLOL is now available at http://localhost:8000

    # Check status
    status = sollol.get_status()
    print(status)

    # Stop when done
    sollol.stop()
    ```
"""
import multiprocessing
import sys

# Force fork mode for Dask on Unix systems BEFORE any imports
if sys.platform != 'win32':
    try:
        multiprocessing.set_start_method('fork', force=True)
    except RuntimeError:
        pass  # Already set

from sollol.sollol import SOLLOL
from sollol.config import SOLLOLConfig
from sollol.client import SOLLOLClient, connect, Ollama
# Distributed execution (new in v0.2.0)
from sollol.tasks import DistributedTask, TaskResult, ExecutionResult
from sollol.execution import DistributedExecutor, AsyncDistributedExecutor
from sollol.aggregation import ResultAggregator

__version__ = "0.2.0"
__all__ = [
    "SOLLOL",
    "SOLLOLConfig",
    "SOLLOLClient",
    "connect",
    "Ollama",  # Zero-config client (new!)
    # Distributed Execution
    "DistributedTask",
    "TaskResult",
    "ExecutionResult",
    "DistributedExecutor",
    "AsyncDistributedExecutor",
    "ResultAggregator"
]
