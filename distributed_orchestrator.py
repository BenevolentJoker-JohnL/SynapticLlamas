from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from agents.researcher import Researcher
from agents.critic import Critic
from agents.editor import Editor
from agents.storyteller import Storyteller
from aggregator import aggregate_metrics
from json_pipeline import merge_json_outputs, validate_json_output
from node_registry import NodeRegistry
from sollol_load_balancer import SOLLOLLoadBalancer  # SOLLOL intelligent routing
from adaptive_strategy import AdaptiveStrategySelector, ExecutionMode
from collaborative_workflow import CollaborativeWorkflow
from load_balancer import RoutingStrategy
# Use SOLLOL's distributed execution (new in v0.2.0)
from sollol import DistributedExecutor, AsyncDistributedExecutor, DistributedTask
from content_detector import detect_content_type, get_continuation_prompt, ContentType
from flockparser_adapter import get_flockparser_adapter
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

    def __init__(self, registry: NodeRegistry = None, use_sollol: bool = True, use_flockparser: bool = False,
                 enable_distributed_inference: bool = False, rpc_backends: list = None,
                 task_distribution_enabled: bool = True):
        """
        Initialize distributed orchestrator with SOLLOL.

        Args:
            registry: NodeRegistry instance (creates default if None)
            use_sollol: Use SOLLOL intelligent routing (default: True)
            use_flockparser: Enable FlockParser RAG enhancement (default: False)
            enable_distributed_inference: Enable llama.cpp distributed inference (default: False)
            rpc_backends: List of RPC backend configs for distributed inference
            task_distribution_enabled: Enable Ollama task distribution (default: True)
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

        # Initialize HybridRouter for distributed inference with llama.cpp
        self.hybrid_router = None
        self.hybrid_router_sync = None
        self.enable_distributed_inference = enable_distributed_inference
        self.task_distribution_enabled = task_distribution_enabled

        if enable_distributed_inference:
            try:
                # Use RayHybridRouter for Ray+Dask distributed execution
                from sollol.ray_hybrid_router import RayHybridRouter
                from sollol.pool import OllamaPool
                from hybrid_router_sync import HybridRouterSync

                # Only create OllamaPool if task distribution is enabled
                ollama_pool = None
                if task_distribution_enabled:
                    # Create OllamaPool from existing registry nodes
                    ollama_nodes = [{"host": node.url.replace("http://", "").split(":")[0],
                                    "port": node.url.split(":")[-1]}
                                   for node in self.registry.nodes.values()]
                    ollama_pool = OllamaPool(nodes=ollama_nodes if ollama_nodes else None)
                    logger.info(f"✅ Task distribution enabled: Ollama pool with {len(ollama_nodes)} nodes")
                else:
                    logger.info("⏭️  Task distribution disabled: Using only RPC model sharding")

                # Create RayHybridRouter (uses Ray for parallel pool execution)
                self.hybrid_router = RayHybridRouter(
                    ollama_pool=ollama_pool,  # None if task distribution disabled
                    rpc_backends=rpc_backends,
                    enable_distributed=True,
                    pool_size=5,  # Ray parallel pool size
                )

                # Create sync wrapper for agents
                self.hybrid_router_sync = HybridRouterSync(self.hybrid_router)

                logger.info(f"✨ Ray+Dask distributed routing enabled")
                logger.info(f"🔗 llama.cpp model sharding enabled with {len(rpc_backends) if rpc_backends else 0} RPC backends")
            except Exception as e:
                logger.error(f"Failed to initialize RayHybridRouter: {e}")
                self.enable_distributed_inference = False

        # Initialize FlockParser RAG adapter
        self.use_flockparser = use_flockparser
        self.flockparser_adapter = None
        if use_flockparser:
            try:
                self.flockparser_adapter = get_flockparser_adapter()
                if self.flockparser_adapter.available:
                    stats = self.flockparser_adapter.get_statistics()
                    logger.info(f"📚 FlockParser RAG enabled ({stats['documents']} documents, {stats['chunks']} chunks)")
                else:
                    logger.warning("⚠️  FlockParser enabled but not available - RAG disabled")
                    self.use_flockparser = False
            except Exception as e:
                logger.warning(f"⚠️  Could not initialize FlockParser: {e}")
                self.use_flockparser = False

        # Initialize SOLLOL distributed execution engine
        if use_sollol:
            self.parallel_executor = DistributedExecutor(self.load_balancer, max_workers=10)
            self.async_executor = AsyncDistributedExecutor(self.load_balancer)
            logger.info("✨ SOLLOL distributed execution engine initialized")

        # Initialize with localhost ONLY if no other nodes exist
        # This allows users to configure remote nodes with higher priority
        if len(self.registry) == 0:
            try:
                self.registry.add_node("http://localhost:11434", name="localhost", priority=10)
                logger.info("Added localhost:11434 to registry (fallback)")
            except Exception as e:
                logger.warning(f"Could not add localhost node: {e}")
        else:
            logger.info(f"Using existing {len(self.registry)} nodes in registry (skipping localhost auto-add)")

    def run(self, input_data: str, model: str = "llama3.2",
            execution_mode: ExecutionMode = None,
            routing_strategy: RoutingStrategy = None,
            collaborative: bool = False,
            refinement_rounds: int = 1,
            timeout: int = 300,
            enable_ast_voting: bool = False,
            quality_threshold: float = 0.7,
            max_quality_retries: int = 2,
            synthesis_model: str = None) -> dict:
        """
        Run agents with intelligent distribution.

        Args:
            input_data: Input text/prompt
            model: Ollama model to use for phases 1-3 (e.g., "llama3.2:8b")
            execution_mode: Force specific execution mode (None = adaptive)
            routing_strategy: Force routing strategy (None = adaptive)
            collaborative: Use collaborative workflow instead of parallel
            refinement_rounds: Number of refinement iterations (collaborative mode)
            timeout: Inference timeout in seconds
            enable_ast_voting: Enable AST quality voting
            quality_threshold: Minimum quality score (0.0-1.0)
            max_quality_retries: Maximum quality re-refinement attempts
            synthesis_model: Optional larger model for phase 4 synthesis (e.g., "llama3.1:70b")

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

            # Run collaborative workflow with SOLLOL load balancer and HybridRouter
            workflow = CollaborativeWorkflow(
                model=model,
                max_refinement_rounds=refinement_rounds,
                distributed=use_distributed,
                node_urls=node_urls,
                timeout=timeout,
                enable_ast_voting=enable_ast_voting,
                quality_threshold=quality_threshold,
                max_quality_retries=max_quality_retries,
                load_balancer=self.load_balancer if self.use_sollol else None,
                synthesis_model=synthesis_model,
                hybrid_router=self.hybrid_router_sync if self.hybrid_router_sync else None
            )
            # Pass http://localhost:11434 as default, but agents will use load balancer if available
            workflow_result = workflow.run(input_data, ollama_url="http://localhost:11434")

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

        # PARALLEL MODE - Auto-detect if we should use true parallel execution
        start_time = time.time()

        # Check if we have multiple healthy nodes for true parallel execution
        healthy_nodes = self.registry.get_healthy_nodes()
        num_nodes = len(healthy_nodes)

        # If we have 2+ nodes, use automatic parallel execution
        if num_nodes >= 2 and execution_mode != ExecutionMode.SINGLE_NODE:
            sep = "=" * 60
            logger.info(f"\n{sep}")
            logger.info(f"🚀 AUTO-PARALLEL MODE: {num_nodes} nodes detected")
            logger.info(f"{sep}\n")
            logger.info(f"   Agents will execute concurrently across nodes")
            logger.info(f"   SOLLOL will distribute load intelligently\n")

            # Create SOLLOL distributed tasks for the 3 standard agents
            tasks = [
                DistributedTask(
                    task_id="Researcher",
                    payload={'prompt': input_data, 'model': model},
                    priority=5,
                    timeout=timeout
                ),
                DistributedTask(
                    task_id="Critic",
                    payload={'prompt': input_data, 'model': model},
                    priority=7,  # Higher priority for critic
                    timeout=timeout
                ),
                DistributedTask(
                    task_id="Editor",
                    payload={'prompt': input_data, 'model': model},
                    priority=6,
                    timeout=timeout
                )
            ]

            # Define execution function for SOLLOL
            def execute_agent_task(task: DistributedTask, node_url: str):
                """Execute an agent task on a specific node."""
                agent = self.get_agent(task.task_id, model=model, timeout=timeout)
                # Set the node URL after creation
                agent.ollama_url = node_url
                # Disable SOLLOL routing since we already routed
                agent._load_balancer = None
                return agent.process(task.payload['prompt'])

            # Execute in parallel with SOLLOL
            result = self.parallel_executor.execute_parallel(
                tasks,
                executor_fn=execute_agent_task,
                merge_strategy="collect"
            )

            # Format result to match expected structure
            sep = "=" * 60
            logger.info(f"\n{sep}")
            logger.info(f"✨ PARALLEL EXECUTION COMPLETE")
            logger.info(f"{sep}\n")
            logger.info(f"⚡ Speedup: {result['statistics']['speedup_factor']:.2f}x")
            logger.info(f"⏱️  Total: {result['statistics']['total_duration_ms']:.0f}ms vs {sum(r.duration_ms for r in result['individual_results']):.0f}ms sequential")
            logger.info(f"📊 Success: {result['statistics']['successful']}/{result['statistics']['total_tasks']} agents\n")

            # Build node attribution
            node_attribution = [
                {
                    'agent': r.agent_name,
                    'node': r.node_url,
                    'time': r.duration_ms / 1000.0
                }
                for r in result['individual_results']
                if r.success
            ]

            # Merge outputs
            json_outputs = [
                {
                    'agent': r.agent_name,
                    'status': 'success' if r.success else 'error',
                    'format': 'json',
                    'data': r.result
                }
                for r in result['individual_results']
            ]

            final_json = merge_json_outputs(json_outputs)

            return {
                'result': final_json,
                'metrics': {
                    'total_execution_time': result['statistics']['total_duration_ms'] / 1000.0,
                    'speedup_factor': result['statistics']['speedup_factor'],
                    'parallel_efficiency': result['statistics']['speedup_factor'] / num_nodes,
                    'mode': 'auto-parallel',
                    'nodes_used': num_nodes,
                    'node_attribution': node_attribution
                },
                'raw_json': json_outputs,
                'strategy_used': {
                    'mode': 'auto-parallel',
                    'nodes': num_nodes,
                    'routing': 'SOLLOL'
                }
            }

        # SEQUENTIAL MODE - fallback when only 1 node or forced
        logger.info(f"📍 Sequential mode: {num_nodes} node(s) available")

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
                agent._hybrid_router_sync = self.hybrid_router_sync  # Enable Ollama/RPC routing
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
                agent._hybrid_router_sync = self.hybrid_router_sync
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


    def run_parallel(
        self,
        prompt: str,
        agent_names: List[str] = None,
        num_agents: int = 3,
        merge_strategy: str = "collect",
        model: str = "llama3.2",
        timeout: int = 300
    ) -> dict:
        """
        Run multiple agents in parallel across distributed nodes.

        This is the main entry point for parallel execution - agents fire off
        concurrently and SOLLOL routes them to optimal nodes.

        Args:
            prompt: The prompt/task for all agents
            agent_names: List of agent names (auto-generates if None)
            num_agents: Number of agents to run (if agent_names not provided)
            merge_strategy: How to combine results ("collect", "vote", "merge", "best")
            model: Ollama model to use
            timeout: Request timeout in seconds

        Returns:
            dict with merged results and statistics
        """
        sep = "=" * 60
        logger.info(f"\n{sep}")
        logger.info(f"🚀 PARALLEL EXECUTION MODE")
        logger.info(f"{sep}\n")

        # Create SOLLOL distributed tasks
        if agent_names is None:
            agent_names = [f"Agent_{i+1}" for i in range(num_agents)]

        tasks = [
            DistributedTask(
                task_id=name,
                payload={'prompt': prompt, 'model': model},
                priority=5,
                timeout=timeout
            )
            for name in agent_names
        ]

        logger.info(f"📋 Created {len(tasks)} parallel tasks")
        logger.info(f"🌐 Available nodes: {[n.url for n in self.registry.get_healthy_nodes()]}\n")

        # Define execution function
        def execute_agent_task(task: DistributedTask, node_url: str):
            agent = self.get_agent(task.task_id, model=model, timeout=timeout)
            agent.ollama_url = node_url
            return agent.process(task.payload['prompt'])

        # Execute in parallel with SOLLOL
        result = self.parallel_executor.execute_parallel(
            tasks,
            executor_fn=execute_agent_task,
            merge_strategy=merge_strategy
        )

        sep = "=" * 60
        logger.info(f"\n{sep}")
        logger.info(f"✨ PARALLEL EXECUTION COMPLETE")
        logger.info(f"{sep}\n")
        logger.info(f"📊 Results: {len(result['individual_results'])} agents completed")
        logger.info(f"⚡ Speedup: {result['statistics']['speedup_factor']:.2f}x")
        logger.info(f"⏱️  Total time: {result['statistics']['total_duration_ms']:.0f}ms")
        logger.info(f"📈 Avg per task: {result['statistics']['avg_task_duration_ms']:.0f}ms\n")

        return result

    def run_brainstorm(
        self,
        prompt: str,
        num_agents: int = 3,
        model: str = "llama3.2"
    ) -> dict:
        """
        Brainstorm solutions by running multiple agents in parallel.

        All agents work on the same prompt simultaneously across different nodes.

        Args:
            prompt: The problem/question to brainstorm
            num_agents: Number of brainstorming agents
            model: Ollama model to use

        Returns:
            dict with collected brainstorming results
        """
        logger.info(f"\n💡 BRAINSTORMING MODE: {num_agents} agents in parallel\n")

        # Create brainstorm tasks
        tasks = [
            DistributedTask(
                task_id=f"Brainstorm_{i+1}",
                payload={'prompt': prompt, 'model': model},
                priority=5,
                timeout=300
            )
            for i in range(num_agents)
        ]

        def execute_brainstorm(task: DistributedTask, node_url: str):
            agent = self.get_agent(task.task_id, model=model)
            agent.ollama_url = node_url
            return agent.process(task.payload['prompt'])

        return self.parallel_executor.execute_parallel(
            tasks,
            executor_fn=execute_brainstorm,
            merge_strategy="collect"
        )

    def run_multi_critic(
        self,
        content: str,
        num_critics: int = 3,
        model: str = "llama3.2"
    ) -> dict:
        """
        Get multiple critical reviews in parallel.

        Args:
            content: Content to review
            num_critics: Number of critic agents
            model: Ollama model to use

        Returns:
            dict with merged critical reviews
        """
        logger.info(f"\n🔍 MULTI-CRITIC MODE: {num_critics} critics in parallel\n")

        # Create critic tasks
        tasks = [
            DistributedTask(
                task_id=f"Critic_{i+1}",
                payload={'prompt': f"Review and critique the following:\n\n{content}", 'model': model},
                priority=7,
                timeout=300
            )
            for i in range(num_critics)
        ]

        def execute_critic(task: DistributedTask, node_url: str):
            agent = self.get_agent(task.task_id, model=model)
            agent.ollama_url = node_url
            return agent.process(task.payload['prompt'])

        return self.parallel_executor.execute_parallel(
            tasks,
            executor_fn=execute_critic,
            merge_strategy="merge"
        )

    def get_agent(self, agent_name: str, model: str = "llama3.2", timeout: int = 300):
        """
        Get or create an agent instance with SOLLOL routing enabled.

        Args:
            agent_name: Agent name/type
            model: Ollama model
            timeout: Request timeout

        Returns:
            Agent instance with SOLLOL routing configured
        """
        # Map agent names to classes
        agent_classes = {
            'researcher': Researcher,
            'critic': Critic,
            'editor': Editor
        }

        # Normalize agent name
        agent_type = agent_name.lower().split('_')[0]

        # Get agent class
        if agent_type in agent_classes:
            AgentClass = agent_classes[agent_type]
        else:
            # Generic agent - use Researcher as fallback
            logger.warning(f"Unknown agent type '{agent_name}', using Researcher")
            AgentClass = Researcher

        # Create agent instance
        agent = AgentClass(
            model=model,
            ollama_url=None,  # Will use SOLLOL routing
            timeout=timeout
        )

        # Override name
        agent.name = agent_name

        # Inject SOLLOL load balancer
        agent._load_balancer = self.load_balancer
        agent._hybrid_router_sync = self.hybrid_router_sync

        return agent


    def run_longform(
        self,
        query: str,
        model: str = "llama3.2",
        auto_detect: bool = True,
        content_type: Optional[ContentType] = None,
        max_chunks: int = 5
    ) -> dict:
        """
        Generate long-form content with automatic multi-turn processing.

        Uses distributed parallel execution for optimal performance across
        research, discussion, and storytelling tasks.

        Args:
            query: User query
            model: Ollama model to use
            auto_detect: Auto-detect content type
            content_type: Force specific content type
            max_chunks: Maximum response chunks

        Returns:
            dict with complete long-form content and metadata
        """
        start_time = time.time()

        # Detect content type and estimate chunks
        if auto_detect:
            detected_type, estimated_chunks, metadata = detect_content_type(query)
            if content_type is None:
                content_type = detected_type
            chunks_needed = min(estimated_chunks, max_chunks)
        else:
            content_type = content_type or ContentType.GENERAL
            chunks_needed = 1
            metadata = {}

        logger.info(f"\n{'='*60}")
        logger.info(f"📚 LONG-FORM GENERATION: {content_type.value.upper()}")
        logger.info(f"{'='*60}\n")
        logger.info(f"   Content Type: {content_type.value}")
        logger.info(f"   Estimated Chunks: {chunks_needed}")
        logger.info(f"   Confidence: {metadata.get('confidence', 0):.2f}\n")

        # Enhance query with FlockParser RAG if enabled and content is research
        source_documents = []
        enhanced_query = query
        if self.use_flockparser and content_type == ContentType.RESEARCH:
            try:
                enhanced_query, source_documents = self.flockparser_adapter.enhance_research_query(
                    query,
                    top_k=15,
                    max_context_tokens=2000
                )
                if source_documents:
                    logger.info(f"📖 RAG Enhancement: Using {len(source_documents)} source document(s)")
                    for doc in source_documents:
                        logger.info(f"   • {doc}")
                    logger.info("")
            except Exception as e:
                logger.warning(f"⚠️  FlockParser enhancement failed: {e}")
                enhanced_query = query

        # Check if we should use parallel generation
        healthy_nodes = self.registry.get_healthy_nodes()
        use_parallel = len(healthy_nodes) >= 2 and chunks_needed > 1

        if use_parallel:
            logger.info(f"⚡ PARALLEL MULTI-TURN MODE: {len(healthy_nodes)} nodes available\n")
            result = self._run_longform_parallel(
                enhanced_query, content_type, chunks_needed, model
            )
        else:
            logger.info(f"📝 SEQUENTIAL MULTI-TURN MODE (insufficient nodes)\n")
            result = self._run_longform_sequential(
                enhanced_query, content_type, chunks_needed, model
            )

        # Add RAG metadata to result
        if source_documents:
            result['metadata'] = result.get('metadata', {})
            result['metadata']['rag_sources'] = source_documents
            result['metadata']['rag_enabled'] = True

        return result

    def _get_focus_areas_for_chunks(self, content_type: ContentType, total_chunks: int) -> dict:
        """
        Assign specific focus areas to each chunk to prevent repetition in parallel generation.

        Returns dict mapping chunk_num -> focus_area description
        """
        if content_type == ContentType.RESEARCH:
            # Research focus areas - MUTUALLY EXCLUSIVE to prevent overlap
            areas = {
                1: "ONLY fundamental concepts, basic definitions, and foundational principles (NO applications, NO experiments, NO math details)",
                2: "ONLY mathematical formalism, equations, theoretical frameworks, and technical mechanisms (NO basic concepts, NO applications)",
                3: "ONLY experimental evidence, empirical studies, observational data, and research findings (NO theory, NO applications)",
                4: "ONLY real-world applications, practical implementations, use cases, and industry adoption (NO theory, NO experiments)",
                5: "ONLY current research frontiers, unsolved problems, controversies, and future research directions (NO basics, NO current applications)"
            }
        elif content_type == ContentType.ANALYSIS:
            areas = {
                1: "overview and initial assessment",
                2: "strengths, advantages, and positive aspects",
                3: "weaknesses, limitations, and challenges",
                4: "comparative analysis and alternatives",
                5: "implications and conclusions"
            }
        elif content_type == ContentType.EXPLANATION:
            areas = {
                1: "basic overview and introduction",
                2: "step-by-step process and methodology",
                3: "common pitfalls and troubleshooting",
                4: "advanced techniques and best practices",
                5: "practical examples and use cases"
            }
        elif content_type == ContentType.DISCUSSION:
            areas = {
                1: "main arguments and initial perspectives",
                2: "alternative viewpoints and counter-arguments",
                3: "evidence and supporting data",
                4: "synthesis and balanced analysis",
                5: "conclusions and implications"
            }
        else:
            # Generic fallback
            areas = {
                1: "introduction and overview",
                2: "core concepts and details",
                3: "examples and applications",
                4: "advanced topics",
                5: "summary and conclusions"
            }

        # Return only the areas we need for this total_chunks count
        return {k: v for k, v in areas.items() if k <= total_chunks}

    def _extract_narrative_from_json(self, content):
        """Extract narrative text from JSON response, filtering out metadata."""
        if content is None:
            return ""

        if isinstance(content, dict):
            # Try to extract narrative content from common keys (in priority order)
            # 'data' is for SOLLOL package agent responses
            # 'story' is for Storyteller agent output
            # 'detailed_explanation' is for Editor synthesis output
            # 'context' is for Researcher agent output
            for key in ['data', 'story', 'detailed_explanation', 'context', 'final_output', 'summary', 'content', 'narrative']:
                if key in content and content[key]:  # Must have actual content
                    return str(content[key])

            # If no known keys found, try to extract ANY string value
            # This handles cases where the JSON uses custom keys like {"The Thread of Time": "story content"}
            for key, value in content.items():
                # Skip metadata keys (short values, lowercase, underscores)
                if isinstance(value, str) and len(value) > 50:  # Narrative content is usually >50 chars
                    if not key.startswith('_') and not key.islower():  # Skip metadata-like keys
                        return str(value)

            # If still no content found, try ANY string value regardless of length
            for key, value in content.items():
                if isinstance(value, str) and value.strip():
                    return str(value)

            # Last resort: log warning
            logger.warning(f"No narrative content found in JSON response. Keys present: {list(content.keys())}")
            return ""

        return str(content) if content else ""

    def _run_longform_parallel(
        self,
        query: str,
        content_type: ContentType,
        chunks_needed: int,
        model: str
    ) -> dict:
        """
        Generate long-form content with parallel chunk generation.

        Strategy:
        1. Generate initial chunk (Part 1)
        2. Generate remaining chunks in parallel, each building on Part 1
        3. Merge and synthesize all chunks into coherent output
        """
        start_time = time.time()
        all_chunks = []

        # Phase 1: Generate initial chunk
        logger.info(f"📝 Phase 1: Initial Content Generation")

        # Get focus areas for parallel generation
        focus_areas = self._get_focus_areas_for_chunks(content_type, chunks_needed)

        # Adapt prompt based on content type
        if content_type == ContentType.STORYTELLING:
            # For creative writing using Storyteller agent
            initial_prompt = f"""Write a creative, engaging story based on this request:

{query}

This is Part 1 of {chunks_needed}. Write at least 200-300 words of actual narrative story content.

IMPORTANT Requirements:
- Follow ALL user requirements (rhyming, style, tone, target audience, etc.)
- Write actual story narrative, not descriptions about a story
- Include vivid descriptions, dialogue, and character development
- Make it engaging and creative

Respond with JSON containing a 'story' field with your narrative."""
        else:
            # For research/discussion/analysis, use focused prompt
            chunk1_focus = focus_areas.get(1, "fundamental concepts")
            initial_prompt = f"""Research topic: {query}

Part 1 of {chunks_needed}. Write 500-600 words focused EXCLUSIVELY on: {chunk1_focus}

CRITICAL REQUIREMENTS:
- Cover ONLY {chunk1_focus} - DO NOT discuss other aspects
- Include technical details, equations, data where relevant
- Provide specific examples with numbers and data
- Be technical and specific, not vague or general
- This is Part 1 of {chunks_needed}, so other parts will cover different aspects

Output JSON with 'context' field containing your detailed explanation as a continuous text string."""

        initial_task = DistributedTask(
            task_id="Initial_Content",
            payload={'prompt': initial_prompt, 'model': model},
            priority=8,  # High priority for initial chunk
            timeout=300
        )

        def execute_chunk(task: DistributedTask, node_url: str):
            # Use Storyteller for creative content, Researcher for analytical
            if content_type == ContentType.STORYTELLING:
                agent = Storyteller(model=model, timeout=300)
            else:
                agent = Researcher(model=model, timeout=300)

            # Inject HybridRouter for intelligent Ollama/RPC routing
            agent._hybrid_router_sync = self.hybrid_router_sync
            agent._load_balancer = None  # Disable load balancer, use HybridRouter instead
            return agent.process(task.payload['prompt'])

        initial_result = self.parallel_executor.execute_parallel(
            [initial_task],
            executor_fn=execute_chunk,
            merge_strategy="collect"
        )

        initial_content = initial_result.merged_result[0] if initial_result.merged_result else ""
        all_chunks.append({
            'chunk_num': 1,
            'content': initial_content,
            'duration_ms': initial_result.statistics['total_duration_ms']
        })

        logger.info(f"   ✅ Initial chunk completed ({initial_result.statistics['total_duration_ms']:.0f}ms)\n")

        # Phase 2: Generate remaining chunks IN PARALLEL with SPECIFIC FOCUS AREAS
        if chunks_needed > 1:
            logger.info(f"⚡ Phase 2: Parallel Chunk Generation ({chunks_needed-1} chunks)")

            # Assign specific focus areas to prevent repetition
            focus_areas = self._get_focus_areas_for_chunks(content_type, chunks_needed)

            # Create continuation tasks for all remaining chunks
            continuation_tasks = []
            for i in range(2, chunks_needed + 1):
                # Use specific focus area instead of generic continuation
                focus = focus_areas.get(i, "additional aspects")

                if content_type == ContentType.STORYTELLING:
                    continuation_prompt = get_continuation_prompt(
                        content_type, i, chunks_needed, initial_content, original_query=query
                    )
                else:
                    # For research, use focused prompts
                    continuation_prompt = f"""Research topic: {query}

Part {i} of {chunks_needed}. Write 500-600 words focused SPECIFICALLY on: {focus}

Previous part covered: {self._extract_narrative_from_json(initial_content)[:200]}...

CRITICAL REQUIREMENTS:
- Focus EXCLUSIVELY on {focus} - DO NOT discuss other aspects
- Write ENTIRELY NEW content - ZERO overlap with Part 1
- Include technical details, equations, data, specific examples
- If you mention something from Part 1, you MUST add NEW information about it
- Be technical and specific, not vague or repetitive

Output JSON with 'context' field containing your detailed explanation."""

                task = DistributedTask(
                    task_id=f"Chunk_{i}",
                    payload={'prompt': continuation_prompt, 'model': model},
                    priority=5,
                    timeout=300
                )
                continuation_tasks.append(task)

            # Execute all continuations in parallel
            continuation_result = self.parallel_executor.execute_parallel(
                continuation_tasks,
                executor_fn=execute_chunk,
                merge_strategy="collect"
            )

            # Add all continuation chunks
            for i, chunk_content in enumerate(continuation_result.merged_result, start=2):
                all_chunks.append({
                    'chunk_num': i,
                    'content': chunk_content,
                    'duration_ms': continuation_result.individual_results[i-2].duration_ms
                })

            logger.info(
                f"   ✅ All chunks completed in parallel "
                f"({continuation_result.statistics['total_duration_ms']:.0f}ms, "
                f"speedup: {continuation_result.statistics['speedup_factor']:.2f}x)\n"
            )

        # Phase 3: Synthesize all chunks into final output
        logger.info(f"🔗 Phase 3: Content Synthesis")

        # Combine all chunks
        combined_content = "\n\n".join([
            f"## Part {chunk['chunk_num']}\n\n{self._extract_narrative_from_json(chunk['content'])}"
            for chunk in all_chunks
        ])

        # Use Editor to synthesize - adapt based on content type
        if content_type == ContentType.STORYTELLING:
            synthesis_prompt = f"""Combine these {chunks_needed} story chapters into one complete, flowing narrative:

{combined_content}

Create a cohesive, well-structured story that flows naturally from beginning to end.
Smooth out transitions between chapters and ensure consistent characterization.

Respond with JSON containing a 'story' field with the complete narrative."""
        else:
            # For research/discussion/analysis, use standard synthesis
            synthesis_prompt = f"Synthesize the following {chunks_needed} parts into a cohesive, comprehensive {content_type.value}:\n\n{combined_content}"

        synthesis_task = DistributedTask(
            task_id="Synthesis",
            payload={
                'prompt': synthesis_prompt,
                'model': model
            },
            priority=9,
            timeout=600
        )

        def execute_synthesis(task: DistributedTask, node_url: str):
            # Use Storyteller for creative synthesis, Editor for analytical
            if content_type == ContentType.STORYTELLING:
                agent = Storyteller(model=model, timeout=600)
            else:
                agent = Editor(model=model, timeout=600)

            # Inject HybridRouter for intelligent Ollama/RPC routing
            agent._hybrid_router_sync = self.hybrid_router_sync
            agent._load_balancer = None  # Disable load balancer, use HybridRouter instead
            return agent.process(task.payload['prompt'])

        synthesis_result = self.parallel_executor.execute_parallel(
            [synthesis_task],
            executor_fn=execute_synthesis,
            merge_strategy="best"
        )

        # Extract narrative from synthesis result
        logger.debug(f"Synthesis merged_result type: {type(synthesis_result.merged_result)}")
        logger.debug(f"Synthesis merged_result value: {synthesis_result.merged_result}")

        final_content = self._extract_narrative_from_json(synthesis_result.merged_result)

        if not final_content or final_content == "None":
            # Fallback: just concatenate the chunks without synthesis
            logger.warning("Synthesis produced empty result, using direct concatenation")
            final_content = "\n\n".join([
                self._extract_narrative_from_json(chunk['content'])
                for chunk in all_chunks
            ])

        total_time = (time.time() - start_time) * 1000

        logger.info(f"   ✅ Synthesis complete ({synthesis_result.statistics['total_duration_ms']:.0f}ms)\n")

        logger.info(f"\n{'='*60}")
        logger.info(f"✨ LONG-FORM GENERATION COMPLETE")
        logger.info(f"{'='*60}\n")
        logger.info(f"   Total Time: {total_time:.0f}ms")
        logger.info(f"   Chunks Generated: {chunks_needed}")
        logger.info(f"   Content Type: {content_type.value}\n")

        # Clean chunks by extracting narratives (remove JSON metadata)
        cleaned_chunks = [
            {
                'chunk_num': chunk['chunk_num'],
                'content': self._extract_narrative_from_json(chunk['content']),
                'duration_ms': chunk['duration_ms']
            }
            for chunk in all_chunks
        ]

        return {
            'result': {
                'final_output': final_content,
                'chunks': cleaned_chunks,
                'content_type': content_type.value
            },
            'metrics': {
                'total_execution_time': total_time / 1000,  # Convert to seconds
                'chunks_generated': chunks_needed,
                'mode': 'parallel_multi_turn'
            }
        }

    def _run_longform_sequential(
        self,
        query: str,
        content_type: ContentType,
        chunks_needed: int,
        model: str
    ) -> dict:
        """
        Generate long-form content sequentially (fallback for single node).
        """
        start_time = time.time()
        all_chunks = []
        accumulated_content = ""

        for chunk_num in range(1, chunks_needed + 1):
            logger.info(f"📝 Generating Chunk {chunk_num}/{chunks_needed}")

            if chunk_num == 1:
                # Use the enhanced initial prompt for first chunk
                if content_type == ContentType.STORYTELLING:
                    prompt = f"""Write a creative, engaging story based on this request:

{query}

This is Part 1 of {chunks_needed}. Write at least 200-300 words of actual narrative story content.

IMPORTANT Requirements:
- Follow ALL user requirements (rhyming, style, tone, target audience, etc.)
- Write actual story narrative, not descriptions about a story
- Include vivid descriptions, dialogue, and character development
- Make it engaging and creative

Respond with JSON containing a 'story' field with your narrative."""
                else:
                    prompt = f"""Research topic: {query}

Part 1 of {chunks_needed}. Write 500-600 words EXCLUSIVELY on fundamental concepts, basic definitions, and foundational principles.

CRITICAL REQUIREMENTS:
- Cover ONLY fundamental concepts and basic principles - DO NOT discuss applications, experiments, or advanced mathematics
- Include technical details and definitions
- Provide specific examples with numbers/data
- Be technical and specific, not vague or general
- This is Part 1, so later parts will cover math formalism, experiments, applications, and future research

Output JSON with 'context' field containing your detailed explanation as a continuous text string."""
            else:
                prompt = get_continuation_prompt(
                    content_type, chunk_num, chunks_needed, accumulated_content, original_query=query
                )

            # Generate chunk with appropriate agent
            if content_type == ContentType.STORYTELLING:
                agent = Storyteller(model=model, timeout=300)
            else:
                agent = Researcher(model=model, timeout=300)

            # Inject HybridRouter for intelligent Ollama/RPC routing
            agent._hybrid_router_sync = self.hybrid_router_sync
            agent._load_balancer = self.load_balancer if self.use_sollol else None

            chunk_start = time.time()
            chunk_content = agent.process(prompt)
            chunk_duration = (time.time() - chunk_start) * 1000

            all_chunks.append({
                'chunk_num': chunk_num,
                'content': chunk_content,
                'duration_ms': chunk_duration
            })

            # Extract narrative for accumulation
            chunk_text = self._extract_narrative_from_json(chunk_content)
            accumulated_content += f"\n\n{chunk_text}"
            logger.info(f"   ✅ Chunk {chunk_num} complete ({chunk_duration:.0f}ms)\n")

        # Synthesize
        logger.info(f"🔗 Synthesizing final output (this may take longer for comprehensive synthesis)")
        if content_type == ContentType.STORYTELLING:
            editor = Storyteller(model=model, timeout=600)
        else:
            editor = Editor(model=model, timeout=600)

        # Inject HybridRouter for intelligent Ollama/RPC routing
        editor._hybrid_router_sync = self.hybrid_router_sync
        editor._load_balancer = self.load_balancer if self.use_sollol else None

        final_content = editor.process(
            f"Synthesize into cohesive {content_type.value}:\n\n{accumulated_content}"
        )

        total_time = (time.time() - start_time) * 1000

        logger.info(f"\n{'='*60}")
        logger.info(f"✨ LONG-FORM GENERATION COMPLETE")
        logger.info(f"{'='*60}\n")

        # Clean chunks by extracting narratives (remove JSON metadata)
        cleaned_chunks = [
            {
                'chunk_num': chunk['chunk_num'],
                'content': self._extract_narrative_from_json(chunk['content']),
                'duration_ms': chunk['duration_ms']
            }
            for chunk in all_chunks
        ]

        return {
            'result': {
                'final_output': self._extract_narrative_from_json(final_content),
                'chunks': cleaned_chunks,
                'content_type': content_type.value
            },
            'metrics': {
                'total_execution_time': total_time / 1000,  # Convert to seconds
                'chunks_generated': chunks_needed,
                'mode': 'sequential_multi_turn'
            }
        }
