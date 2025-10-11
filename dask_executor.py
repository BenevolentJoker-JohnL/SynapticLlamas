import logging
from typing import List, Dict, Optional
import time
from dask.distributed import Client, as_completed
from agents.researcher import Researcher
from agents.critic import Critic
from agents.editor import Editor
from aggregator import aggregate_metrics
from json_pipeline import merge_json_outputs, validate_json_output
from node_registry import NodeRegistry
from load_balancer import OllamaLoadBalancer

logger = logging.getLogger(__name__)


class DaskDistributedExecutor:
    """
    Dask-based distributed executor for true multi-machine processing.
    Uses Ollama load balancer for inference routing.
    """

    def __init__(self, dask_scheduler: Optional[str] = None, registry: NodeRegistry = None):
        """
        Initialize Dask executor.

        Args:
            dask_scheduler: Dask scheduler address (e.g., 'tcp://192.168.1.50:8786')
                           If None, creates a local cluster
            registry: NodeRegistry for Ollama load balancing
        """
        self.registry = registry or NodeRegistry()
        self.load_balancer = OllamaLoadBalancer(self.registry)

        # Initialize Dask client
        if dask_scheduler:
            logger.info(f"Connecting to Dask scheduler: {dask_scheduler}")
            self.client = Client(dask_scheduler)
        else:
            logger.info("Starting local Dask cluster")
            # Create LocalCluster with extended session token expiration (1 year)
            from dask.distributed import LocalCluster
            cluster = LocalCluster(
                dashboard_address=":8787",
                silence_logs=logging.ERROR,
                # Bokeh server config for dashboard - set token expiration to 1 year
                extra_dashboard_args=["--session-token-expiration=31536000000"]  # 1 year in milliseconds
            )
            self.client = Client(cluster)

        logger.info(f"Dask cluster ready: {self.client.dashboard_link}")

        # Ensure localhost Ollama node exists
        if len(self.registry) == 0:
            try:
                self.registry.add_node("http://localhost:11434", name="localhost", priority=10)
            except Exception as e:
                logger.warning(f"Could not add localhost node: {e}")

    def run(self, input_data: str, model: str = "llama3.2") -> Dict:
        """
        Execute agents distributed across Dask workers.
        Uses Ollama load balancer for inference.

        Args:
            input_data: Input text/prompt
            model: Ollama model to use

        Returns:
            dict with 'result', 'metrics', 'raw_json', 'dask_info'
        """
        start_time = time.time()

        # Create agent tasks
        agent_configs = [
            {"type": "Researcher", "model": model},
            {"type": "Critic", "model": model},
            {"type": "Editor", "model": model}
        ]

        logger.info(f"🚀 Submitting {len(agent_configs)} agents to Dask cluster")

        # Submit tasks to Dask
        futures = []
        for config in agent_configs:
            future = self.client.submit(
                execute_agent_task,
                agent_type=config["type"],
                input_data=input_data,
                model=config["model"],
                ollama_nodes=self._get_node_urls(),
                pure=False  # Don't cache results
            )
            futures.append(future)

        # Collect results as they complete
        json_outputs = []
        metrics = []
        dask_task_info = []

        for future in as_completed(futures):
            try:
                result = future.result()

                if result['success']:
                    json_outputs.append(result['output'])
                    metrics.append(result['metrics'])

                    logger.info(f"✅ {result['agent_type']} completed on worker "
                               f"{result['worker']} in {result['execution_time']:.2f}s")

                    dask_task_info.append({
                        "agent": result['agent_type'],
                        "worker": result['worker'],
                        "ollama_node": result['ollama_node'],
                        "execution_time": result['execution_time']
                    })
                else:
                    error_output = {
                        "agent": result['agent_type'],
                        "status": "error",
                        "format": "text",
                        "data": {"error": result.get('error', 'Unknown error')}
                    }
                    json_outputs.append(error_output)
                    logger.error(f"❌ {result['agent_type']} failed: {result.get('error')}")

            except Exception as e:
                logger.error(f"Task failed: {e}")
                error_output = {
                    "agent": "Unknown",
                    "status": "error",
                    "format": "text",
                    "data": {"error": str(e)}
                }
                json_outputs.append(error_output)

        # Aggregate results
        final_json = merge_json_outputs(json_outputs)
        final_metrics = aggregate_metrics(metrics)

        total_time = time.time() - start_time

        logger.info(f"✅ All agents completed. Total time: {total_time:.2f}s")

        return {
            'result': final_json,
            'metrics': final_metrics,
            'raw_json': json_outputs,
            'dask_info': {
                'total_time': total_time,
                'tasks': dask_task_info,
                'dashboard': self.client.dashboard_link,
                'workers': len(self.client.scheduler_info()['workers'])
            }
        }

    def _get_node_urls(self) -> List[str]:
        """Get list of healthy Ollama node URLs."""
        healthy = self.registry.get_healthy_nodes()
        return [node.url for node in healthy]

    def close(self):
        """Close Dask client."""
        self.client.close()
        logger.info("Dask client closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def execute_agent_task(agent_type: str, input_data: str, model: str,
                       ollama_nodes: List[str]) -> Dict:
    """
    Execute a single agent task on a Dask worker.
    This function runs remotely on Dask workers.

    Args:
        agent_type: Type of agent (Researcher, Critic, Editor)
        input_data: Input text
        model: Model name
        ollama_nodes: List of available Ollama node URLs

    Returns:
        Result dict
    """
    import socket
    import random
    from agents.researcher import Researcher
    from agents.critic import Critic
    from agents.editor import Editor

    worker_name = socket.gethostname()

    # Select Ollama node (simple round-robin for now)
    if not ollama_nodes:
        return {
            'success': False,
            'agent_type': agent_type,
            'worker': worker_name,
            'error': 'No Ollama nodes available'
        }

    ollama_url = random.choice(ollama_nodes)

    # Create agent
    if agent_type == "Researcher":
        agent = Researcher(model)
    elif agent_type == "Critic":
        agent = Critic(model)
    elif agent_type == "Editor":
        agent = Editor(model)
    else:
        return {
            'success': False,
            'agent_type': agent_type,
            'worker': worker_name,
            'error': f'Unknown agent type: {agent_type}'
        }

    # Set Ollama URL
    agent.ollama_url = ollama_url

    # Execute
    try:
        start = time.time()
        output = agent.process(input_data)
        execution_time = time.time() - start

        return {
            'success': True,
            'agent_type': agent_type,
            'worker': worker_name,
            'ollama_node': ollama_url,
            'output': output,
            'metrics': agent.get_metrics(),
            'execution_time': execution_time
        }

    except Exception as e:
        return {
            'success': False,
            'agent_type': agent_type,
            'worker': worker_name,
            'ollama_node': ollama_url,
            'error': str(e)
        }
