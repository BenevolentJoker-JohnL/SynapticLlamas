from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.researcher import Researcher
from agents.critic import Critic
from agents.editor import Editor
from aggregator import aggregate_metrics
from json_pipeline import merge_json_outputs, validate_json_output
from node_registry import NodeRegistry
from sollol_load_balancer import SOLLOLLoadBalancer  # SOLLOL intelligent routing
from adaptive_strategy import AdaptiveStrategySelector, ExecutionMode
from collaborative_workflow import CollaborativeWorkflow
from load_balancer import RoutingStrategy
import logging
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DistributedOrchestrator:
    """
    Advanced orchestrator with SOLLOL intelligent load balancing.

    Automatically integrates:
    - Context-aware request routing
    - Priority-based scheduling
    - Multi-factor host scoring
    - Adaptive learning
    - Performance tracking
    """

    def __init__(self, registry: NodeRegistry = None, use_sollol: bool = True):
        """
        Initialize distributed orchestrator with SOLLOL.

        Args:
            registry: NodeRegistry instance (creates default if None)
            use_sollol: Use SOLLOL intelligent routing (default: True)
        """
        self.registry = registry or NodeRegistry()

        # Use SOLLOL load balancer for intelligent routing
        if use_sollol:
            self.load_balancer = SOLLOLLoadBalancer(self.registry)
            logger.info("🚀 SOLLOL intelligent routing enabled")
        else:
            from load_balancer import OllamaLoadBalancer, RoutingStrategy
            self.load_balancer = OllamaLoadBalancer(self.registry)
            logger.info("⚙️  Using basic load balancer")

        self.adaptive_selector = AdaptiveStrategySelector(self.registry)
        self.use_sollol = use_sollol

        # Initialize with localhost if no nodes
        if len(self.registry) == 0:
            try:
                self.registry.add_node("http://localhost:11434", name="localhost", priority=10)
            except Exception as e:
                logger.warning(f"Could not add localhost node: {e}")

    def run(self, input_data: str, model: str = "llama3.2",
            execution_mode: ExecutionMode = None,
            routing_strategy: RoutingStrategy = None,
            collaborative: bool = False,
            refinement_rounds: int = 1,
            timeout: int = 300,
            enable_ast_voting: bool = False,
            quality_threshold: float = 0.7,
            max_quality_retries: int = 2) -> dict:
        """
        Run agents with intelligent distribution.

        Args:
            input_data: Input text/prompt
            model: Ollama model to use
            execution_mode: Force specific execution mode (None = adaptive)
            routing_strategy: Force routing strategy (None = adaptive)
            collaborative: Use collaborative workflow instead of parallel
            refinement_rounds: Number of refinement iterations (collaborative mode)

        Returns:
            dict with 'result', 'metrics', 'raw_json', 'strategy_used'
        """
        start_time = time.time()

        # COLLABORATIVE MODE
        if collaborative:
            logger.info("🤝 Using collaborative workflow mode")

            # Get all healthy nodes for distributed refinement
            healthy_nodes = self.registry.get_healthy_nodes()

            if not healthy_nodes:
                raise RuntimeError("No nodes available for collaborative workflow")

            # Primary node for sequential phases
            primary_node = self.load_balancer.get_node(strategy=routing_strategy or RoutingStrategy.LEAST_LOADED)

            # Collect node URLs for distributed refinement
            node_urls = [node.url for node in healthy_nodes]

            # Enable distributed mode if we have multiple nodes
            use_distributed = len(node_urls) > 1

            if use_distributed:
                logger.info(f"🚀 Distributed collaborative mode: {len(node_urls)} nodes available")
            else:
                logger.info(f"📍 Single-node collaborative mode")

            # Run collaborative workflow
            workflow = CollaborativeWorkflow(
                model=model,
                max_refinement_rounds=refinement_rounds,
                distributed=use_distributed,
                node_urls=node_urls,
                timeout=timeout,
                enable_ast_voting=enable_ast_voting,
                quality_threshold=quality_threshold,
                max_quality_retries=max_quality_retries
            )
            workflow_result = workflow.run(input_data, ollama_url=primary_node.url)

            total_time = time.time() - start_time

            # Format output to match expected structure
            node_attribution = []
            if use_distributed and len(node_urls) > 1:
                # Show distributed node usage
                for i, url in enumerate(node_urls[:refinement_rounds]):
                    node_attribution.append({
                        'agent': f'Refinement-{i}',
                        'node': url,
                        'time': 0  # Not tracked individually in collaborative
                    })
            else:
                node_attribution.append({
                    'agent': 'Collaborative-Workflow',
                    'node': f"{primary_node.name} ({primary_node.url})",
                    'time': total_time
                })

            return {
                'result': {
                    'pipeline': 'SynapticLlamas-Collaborative',
                    'workflow': 'sequential-collaborative',
                    'final_output': workflow_result['final_output'],
                    'conversation_history': workflow_result['conversation_history'],
                    'workflow_summary': workflow_result['workflow_summary']
                },
                'metrics': {
                    'total_execution_time': total_time,
                    'mode': 'collaborative',
                    'node_used': primary_node.name,
                    'refinement_rounds': refinement_rounds,
                    'node_attribution': node_attribution,
                    'phase_timings': workflow_result.get('phase_timings', []),
                    'quality_scores': workflow_result.get('quality_scores'),
                    'quality_passed': workflow_result.get('quality_passed', True)
                },
                'raw_json': workflow_result['conversation_history'],
                'strategy_used': {
                    'mode': 'collaborative',
                    'node': primary_node.name,
                    'refinement_rounds': refinement_rounds
                }
            }

        # PARALLEL MODE (existing behavior)
        start_time = time.time()

        # Initialize agents
        agents = [
            Researcher(model, timeout=timeout),
            Critic(model, timeout=timeout),
            Editor(model, timeout=timeout)
        ]

        # Inject SOLLOL load balancer into agents for intelligent routing
        if self.use_sollol:
            for agent in agents:
                agent._load_balancer = self.load_balancer
                logger.debug(f"✅ SOLLOL injected into {agent.name}")

        # Select strategy
        strategy = self.adaptive_selector.select_strategy(
            agent_count=len(agents),
            force_mode=execution_mode
        )

        if routing_strategy:
            strategy['routing_strategy'] = routing_strategy

        logger.info(f"🚀 Executing with strategy: {strategy['mode'].value}")

        # Execute based on mode
        if strategy['mode'] == ExecutionMode.SINGLE_NODE:
            result = self._execute_single_node(agents, input_data, strategy)

        elif strategy['mode'] == ExecutionMode.PARALLEL_SAME_NODE:
            result = self._execute_parallel_same_node(agents, input_data, strategy)

        elif strategy['mode'] == ExecutionMode.PARALLEL_MULTI_NODE:
            result = self._execute_parallel_multi_node(agents, input_data, strategy)

        elif strategy['mode'] == ExecutionMode.GPU_ROUTING:
            result = self._execute_gpu_routing(agents, input_data, strategy)

        else:
            # Fallback to parallel same node
            result = self._execute_parallel_same_node(agents, input_data, strategy)

        # Record benchmark
        total_time = time.time() - start_time
        self.adaptive_selector.record_benchmark(
            mode=strategy['mode'],
            total_time=total_time,
            agent_count=len(agents),
            node_count=strategy['node_count'],
            success=True
        )

        result['strategy_used'] = strategy
        return result

    def _execute_single_node(self, agents, input_data, strategy) -> dict:
        """Execute all agents sequentially on a single node."""
        node = self.load_balancer.get_node(strategy=strategy['routing_strategy'])

        if not node:
            raise RuntimeError("No nodes available")

        logger.info(f"📍 Using node: {node.name}")

        json_outputs = []
        metrics = []
        node_info = []

        # Inject SOLLOL for intelligent routing (even in single node mode)
        if self.use_sollol:
            for agent in agents:
                agent._load_balancer = self.load_balancer
        else:
            # Set agents to use this specific node
            for agent in agents:
                agent.ollama_url = node.url

        for agent in agents:
            try:
                json_result = agent.process(input_data)

                if validate_json_output(json_result):
                    json_outputs.append(json_result)
                    logger.info(f"{agent.name} completed on {node.name} in {agent.execution_time:.2f}s")
                else:
                    logger.warning(f"{agent.name} output validation failed")
                    json_outputs.append(json_result)

                metrics.append(agent.get_metrics())
                node_info.append({
                    'agent': agent.name,
                    'node': f"{node.name} ({node.url})",
                    'time': agent.execution_time
                })

            except Exception as e:
                error_output = {
                    "agent": agent.name,
                    "status": "error",
                    "format": "text",
                    "data": {"error": str(e)}
                }
                json_outputs.append(error_output)
                logger.error(f"{agent.name} failed: {e}")

        final_json = merge_json_outputs(json_outputs)
        final_metrics = aggregate_metrics(metrics)
        final_metrics['node_attribution'] = node_info

        return {
            'result': final_json,
            'metrics': final_metrics,
            'raw_json': json_outputs
        }

    def _execute_parallel_same_node(self, agents, input_data, strategy) -> dict:
        """Execute all agents in parallel on the same node."""
        node = self.load_balancer.get_node(strategy=strategy['routing_strategy'])

        if not node:
            raise RuntimeError("No nodes available")

        logger.info(f"📍 Using node: {node.name} (parallel execution)")

        # Set all agents to use this node
        for agent in agents:
            agent.ollama_url = node.url

        json_outputs = []
        metrics = []
        node_info = []

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            future_to_agent = {executor.submit(agent.process, input_data): agent for agent in agents}

            for future in as_completed(future_to_agent):
                agent = future_to_agent[future]
                try:
                    json_result = future.result()

                    if validate_json_output(json_result):
                        json_outputs.append(json_result)
                        logger.info(f"{agent.name} completed on {node.name} in {agent.execution_time:.2f}s")
                    else:
                        logger.warning(f"{agent.name} output validation failed")
                        json_outputs.append(json_result)

                    metrics.append(agent.get_metrics())
                    node_info.append({
                        'agent': agent.name,
                        'node': f"{node.name} ({node.url})",
                        'time': agent.execution_time
                    })

                except Exception as e:
                    error_output = {
                        "agent": agent.name,
                        "status": "error",
                        "format": "text",
                        "data": {"error": str(e)}
                    }
                    json_outputs.append(error_output)
                    logger.error(f"{agent.name} failed: {e}")

        final_json = merge_json_outputs(json_outputs)
        final_metrics = aggregate_metrics(metrics)
        final_metrics['node_attribution'] = node_info

        return {
            'result': final_json,
            'metrics': final_metrics,
            'raw_json': json_outputs
        }

    def _execute_parallel_multi_node(self, agents, input_data, strategy) -> dict:
        """Execute agents distributed across multiple nodes."""
        nodes = self.load_balancer.get_nodes(
            count=len(agents),
            strategy=strategy['routing_strategy']
        )

        if not nodes:
            raise RuntimeError("No nodes available")

        logger.info(f"📍 Distributing across {len(nodes)} nodes")

        # Assign agents to nodes (round-robin if more agents than nodes)
        agent_node_pairs = []
        for i, agent in enumerate(agents):
            node = nodes[i % len(nodes)]
            agent.ollama_url = node.url
            agent_node_pairs.append((agent, node))
            logger.info(f"  {agent.name} → {node.name}")

        json_outputs = []
        metrics = []
        node_info = []

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            future_to_agent = {executor.submit(agent.process, input_data): (agent, node)
                              for agent, node in agent_node_pairs}

            for future in as_completed(future_to_agent):
                agent, node = future_to_agent[future]
                try:
                    json_result = future.result()

                    if validate_json_output(json_result):
                        json_outputs.append(json_result)
                        logger.info(f"{agent.name} completed on {node.name} in {agent.execution_time:.2f}s")
                    else:
                        logger.warning(f"{agent.name} output validation failed")
                        json_outputs.append(json_result)

                    metrics.append(agent.get_metrics())
                    node_info.append({
                        'agent': agent.name,
                        'node': f"{node.name} ({node.url})",
                        'time': agent.execution_time
                    })

                except Exception as e:
                    error_output = {
                        "agent": agent.name,
                        "status": "error",
                        "format": "text",
                        "data": {"error": str(e)}
                    }
                    json_outputs.append(error_output)
                    logger.error(f"{agent.name} failed on {node.name}: {e}")

        final_json = merge_json_outputs(json_outputs)
        final_metrics = aggregate_metrics(metrics)
        final_metrics['node_attribution'] = node_info

        return {
            'result': final_json,
            'metrics': final_metrics,
            'raw_json': json_outputs
        }

    def _execute_gpu_routing(self, agents, input_data, strategy) -> dict:
        """Route agents to GPU nodes specifically."""
        gpu_nodes = self.registry.get_gpu_nodes()

        if not gpu_nodes:
            logger.warning("No GPU nodes available, falling back to regular nodes")
            return self._execute_parallel_multi_node(agents, input_data, strategy)

        logger.info(f"📍 Routing to {len(gpu_nodes)} GPU nodes")

        # Assign agents to GPU nodes
        agent_node_pairs = []
        for i, agent in enumerate(agents):
            node = gpu_nodes[i % len(gpu_nodes)]
            agent.ollama_url = node.url
            agent_node_pairs.append((agent, node))
            logger.info(f"  {agent.name} → {node.name} 🎮")

        json_outputs = []
        metrics = []
        node_info = []

        # Execute in parallel
        with ThreadPoolExecutor(max_workers=len(agents)) as executor:
            future_to_agent = {executor.submit(agent.process, input_data): (agent, node)
                              for agent, node in agent_node_pairs}

            for future in as_completed(future_to_agent):
                agent, node = future_to_agent[future]
                try:
                    json_result = future.result()

                    if validate_json_output(json_result):
                        json_outputs.append(json_result)
                        logger.info(f"{agent.name} completed on {node.name} in {agent.execution_time:.2f}s")
                    else:
                        logger.warning(f"{agent.name} output validation failed")
                        json_outputs.append(json_result)

                    metrics.append(agent.get_metrics())
                    node_info.append({
                        'agent': agent.name,
                        'node': f"{node.name} ({node.url}) 🎮",
                        'time': agent.execution_time
                    })

                except Exception as e:
                    error_output = {
                        "agent": agent.name,
                        "status": "error",
                        "format": "text",
                        "data": {"error": str(e)}
                    }
                    json_outputs.append(error_output)
                    logger.error(f"{agent.name} failed on {node.name}: {e}")

        final_json = merge_json_outputs(json_outputs)
        final_metrics = aggregate_metrics(metrics)
        final_metrics['node_attribution'] = node_info

        return {
            'result': final_json,
            'metrics': final_metrics,
            'raw_json': json_outputs
        }
