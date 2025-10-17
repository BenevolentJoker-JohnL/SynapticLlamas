"""
SOLLOL Main Orchestration Class - Application-friendly API.

This module provides a programmatic interface for applications to configure
and control SOLLOL entirely from within Python code, without CLI or external configs.
"""
import asyncio
import threading
from typing import Optional, Dict, Any
from datetime import datetime

from sollol.config import SOLLOLConfig
from sollol.cluster import start_ray, start_dask


class SOLLOL:
    """
    Main SOLLOL orchestration class.

    Provides a simple, application-friendly API for managing SOLLOL entirely
    from within your application code.

    Example:
        ```python
        from sollol import SOLLOL, SOLLOLConfig

        # Configure SOLLOL for your application
        config = SOLLOLConfig(
            ray_workers=4,
            dask_workers=4,
            hosts=["10.0.0.2:11434", "10.0.0.3:11434"],
            autobatch_interval=30,
            routing_strategy="performance"
        )

        # Initialize and start
        sollol = SOLLOL(config)
        sollol.start()

        # Your app can now use SOLLOL via the gateway
        # http://localhost:8000/api/chat

        # Update configuration dynamically
        sollol.update_config(ray_workers=6)

        # Check status
        status = sollol.get_status()
        print(status)

        # Stop when done
        sollol.stop()
        ```
    """

    def __init__(self, config: Optional[SOLLOLConfig] = None):
        """
        Initialize SOLLOL with configuration.

        Args:
            config: SOLLOLConfig instance. If None, uses default configuration.
        """
        self.config = config or SOLLOLConfig()
        self.config.validate()

        # Internal state
        self._ray_actors = []
        self._dask_client = None
        self._gateway_thread: Optional[threading.Thread] = None
        self._running = False
        self._initialized = False

        print(f"[SOLLOL] Initialized with configuration:")
        print(f"  Ray workers: {self.config.ray_workers}")
        print(f"  Dask workers: {self.config.dask_workers}")
        print(f"  Hosts: {', '.join(self.config.hosts)}")
        print(f"  Routing: {self.config.routing_strategy}")
        print(f"  Gateway: {self.config.gateway_host}:{self.config.gateway_port}")
        print()

    def _initialize_clusters(self):
        """Initialize Ray and Dask clusters."""
        if self._initialized:
            print("[SOLLOL] Already initialized, skipping...")
            return

        print("[SOLLOL] Initializing clusters...")

        # Create temporary hosts file from config
        import tempfile
        import os

        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            for host in self.config.hosts:
                f.write(f"{host}\n")
            hosts_file = f.name

        try:
            # Initialize Ray cluster
            self._ray_actors = start_ray(
                workers=self.config.ray_workers,
                hosts_file=hosts_file
            )

            if not self._ray_actors:
                raise RuntimeError("Failed to initialize Ray workers")

            # Initialize Dask cluster
            self._dask_client = start_dask(
                workers=self.config.dask_workers,
                scheduler_address=self.config.dask_scheduler
            )

            self._initialized = True
            print("[SOLLOL] Clusters initialized successfully\n")

        finally:
            # Clean up temporary hosts file
            if os.path.exists(hosts_file):
                os.unlink(hosts_file)

    def start(self, blocking: bool = False):
        """
        Start SOLLOL orchestration.

        Args:
            blocking: If True, blocks until stopped. If False, runs in background thread.

        Example:
            ```python
            # Non-blocking (recommended for applications)
            sollol.start(blocking=False)
            # Your app code continues here...

            # Blocking (recommended for standalone SOLLOL service)
            sollol.start(blocking=True)
            ```
        """
        if self._running:
            print("[SOLLOL] Already running")
            return

        # Initialize clusters if not already done
        self._initialize_clusters()

        print("[SOLLOL] Starting gateway...")

        if blocking:
            # Run gateway in current thread (blocks)
            self._start_gateway()
        else:
            # Run gateway in background thread
            self._gateway_thread = threading.Thread(
                target=self._start_gateway,
                daemon=True
            )
            self._gateway_thread.start()
            self._running = True
            print(f"[SOLLOL] Gateway started in background")
            print(f"[SOLLOL] API available at http://localhost:{self.config.gateway_port}")
            print(f"[SOLLOL] Metrics available at http://localhost:{self.config.metrics_port}/metrics")
            print()

    def _start_gateway(self):
        """Internal method to start the FastAPI gateway."""
        from sollol.gateway import start_api

        self._running = True

        start_api(
            ray_actors=self._ray_actors,
            dask_client=self._dask_client,
            port=self.config.gateway_port,
            enable_autobatch=self.config.autobatch_enabled,
            autobatch_interval=self.config.autobatch_interval,
            enable_adaptive_metrics=self.config.adaptive_metrics_enabled,
            adaptive_metrics_interval=self.config.adaptive_metrics_interval
        )

    def stop(self):
        """
        Stop SOLLOL orchestration.

        Note: For MVP, Ray and Dask processes need to be killed manually:
            - Ray: pkill -f "ray::"
            - Dask: pkill -f "dask"
        """
        print("[SOLLOL] Stopping orchestration...")
        self._running = False

        if self._gateway_thread and self._gateway_thread.is_alive():
            print("[SOLLOL] Gateway thread is running in background")
            print("[SOLLOL] Note: Gateway cannot be stopped gracefully in background mode")
            print("[SOLLOL] To stop completely, restart your application or kill processes:")
            print("  pkill -f 'ray::'")
            print("  pkill -f 'dask'")

        print("[SOLLOL] Stopped")

    def update_config(self, **kwargs):
        """
        Update configuration dynamically.

        Args:
            **kwargs: Configuration parameters to update (see SOLLOLConfig for available options)

        Example:
            ```python
            sollol.update_config(
                ray_workers=6,
                autobatch_interval=45,
                routing_strategy="priority"
            )
            ```

        Note: Some configuration changes (like ray_workers, dask_workers) require
        restarting SOLLOL to take effect.
        """
        print("[SOLLOL] Updating configuration...")

        # Update config object
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                old_value = getattr(self.config, key)
                setattr(self.config, key, value)
                print(f"  {key}: {old_value} -> {value}")
            else:
                raise KeyError(f"Invalid configuration key: {key}")

        # Validate new configuration
        self.config.validate()

        # Warn about changes that require restart
        restart_required_keys = {
            "ray_workers", "dask_workers", "dask_scheduler",
            "hosts", "gateway_port", "metrics_port"
        }
        if any(key in restart_required_keys for key in kwargs.keys()):
            print("\n⚠️  Some changes require restarting SOLLOL to take effect:")
            print("  sollol.stop()")
            print("  sollol.start()")

        print()

    def get_status(self) -> Dict[str, Any]:
        """
        Get current SOLLOL status.

        Returns:
            Dictionary containing current status information

        Example:
            ```python
            status = sollol.get_status()
            print(f"Running: {status['running']}")
            print(f"Ray workers: {status['ray_workers']}")
            print(f"Hosts: {status['hosts']}")
            ```
        """
        return {
            "running": self._running,
            "initialized": self._initialized,
            "config": self.config.to_dict(),
            "ray_workers": len(self._ray_actors),
            "ray_actors_initialized": len(self._ray_actors) > 0,
            "dask_initialized": self._dask_client is not None,
            "timestamp": datetime.now().isoformat(),
            "endpoints": {
                "gateway": f"http://localhost:{self.config.gateway_port}",
                "api_docs": f"http://localhost:{self.config.gateway_port}/docs",
                "health": f"http://localhost:{self.config.gateway_port}/api/health",
                "stats": f"http://localhost:{self.config.gateway_port}/api/stats",
                "metrics": f"http://localhost:{self.config.metrics_port}/metrics",
            }
        }

    def get_health(self) -> Dict[str, Any]:
        """
        Get health status from the gateway.

        Returns:
            Health information from /api/health endpoint

        Note: Only works when SOLLOL is running.
        """
        if not self._running:
            return {"error": "SOLLOL is not running"}

        import httpx

        try:
            resp = httpx.get(
                f"http://localhost:{self.config.gateway_port}/api/health",
                timeout=5.0
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """
        Get performance statistics from the gateway.

        Returns:
            Statistics from /api/stats endpoint

        Note: Only works when SOLLOL is running.
        """
        if not self._running:
            return {"error": "SOLLOL is not running"}

        import httpx

        try:
            resp = httpx.get(
                f"http://localhost:{self.config.gateway_port}/api/stats",
                timeout=5.0
            )
            return resp.json()
        except Exception as e:
            return {"error": str(e)}

    def __repr__(self) -> str:
        """String representation of SOLLOL instance."""
        return (
            f"SOLLOL(running={self._running}, "
            f"ray_workers={len(self._ray_actors)}, "
            f"hosts={len(self.config.hosts)}, "
            f"routing={self.config.routing_strategy})"
        )
