import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
from node_registry import NodeRegistry
from load_balancer import RoutingStrategy

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """Execution modes for agent processing."""
    SINGLE_NODE = "single_node"          # All agents on one node (sequential)
    PARALLEL_SAME_NODE = "parallel_same" # All agents parallel on same node
    PARALLEL_MULTI_NODE = "parallel_multi" # Agents distributed across nodes
    GPU_ROUTING = "gpu_routing"          # Route to GPU nodes specifically


@dataclass
class BenchmarkResult:
    """Results from a benchmark run."""
    mode: ExecutionMode
    total_time: float
    avg_time_per_agent: float
    throughput: float  # agents per second
    node_count: int
    success: bool


class AdaptiveStrategySelector:
    """
    Intelligently selects execution strategy based on:
    - Available nodes
    - GPU availability
    - Historical performance
    - Input characteristics
    """

    def __init__(self, registry: NodeRegistry):
        self.registry = registry
        self.benchmark_history: Dict[ExecutionMode, List[BenchmarkResult]] = {
            mode: [] for mode in ExecutionMode
        }
        self._benchmarked = False

    def select_strategy(self, agent_count: int, force_mode: Optional[ExecutionMode] = None) -> Dict:
        """
        Intelligently select optimal execution strategy based on:
        - System resources (nodes, GPU, health)
        - Historical performance data
        - Current load conditions
        - Agent count and complexity

        Args:
            agent_count: Number of agents to execute
            force_mode: Force specific execution mode

        Returns:
            Strategy dict with mode, nodes, and routing_strategy
        """
        if force_mode:
            logger.info(f"🎯 Strategy forced: {force_mode.value}")
            return self._build_strategy(force_mode, agent_count)

        # Get real-time system state
        healthy_nodes = self.registry.get_healthy_nodes()
        gpu_nodes = self.registry.get_gpu_nodes()

        if not healthy_nodes:
            raise RuntimeError("No healthy nodes available")

        # Calculate node health scores
        node_health_scores = [node.calculate_load_score() for node in healthy_nodes]
        avg_health = sum(node_health_scores) / len(node_health_scores)

        # Check if nodes are overloaded
        overloaded = avg_health > 0.7  # Above 70% load

        logger.info(f"📊 System state: {len(healthy_nodes)} nodes, {len(gpu_nodes)} GPU, "
                   f"avg load: {avg_health:.2f}")

        # INTELLIGENT DECISION TREE

        # 1. Single node scenario
        if len(healthy_nodes) == 1:
            node = healthy_nodes[0]
            # If node is overloaded, use sequential to avoid overwhelming it
            if node.calculate_load_score() > 0.8:
                mode = ExecutionMode.SINGLE_NODE
                logger.info("⚠️  Node heavily loaded, using sequential execution")
            else:
                # Choose based on historical performance
                mode = self._choose_single_node_mode(agent_count)

        # 2. GPU available - but check if worth it
        elif len(gpu_nodes) > 0 and agent_count <= len(gpu_nodes):
            # Check GPU node performance history
            if self._benchmarked:
                gpu_perf = self._get_avg_performance(ExecutionMode.GPU_ROUTING)
                multi_perf = self._get_avg_performance(ExecutionMode.PARALLEL_MULTI_NODE)

                # Only use GPU if it's actually faster
                if gpu_perf and multi_perf and gpu_perf > multi_perf * 1.2:
                    mode = ExecutionMode.GPU_ROUTING
                    logger.info("🎮 GPU routing selected (proven faster)")
                else:
                    mode = ExecutionMode.PARALLEL_MULTI_NODE
                    logger.info("📡 Multi-node selected (GPU not significantly faster)")
            else:
                # No benchmark data, prefer GPU
                mode = ExecutionMode.GPU_ROUTING
                logger.info("🎮 GPU routing selected (no benchmark data)")

        # 3. Enough nodes for full distribution
        elif len(healthy_nodes) >= agent_count:
            # Check if nodes are healthy enough for distribution
            if overloaded:
                # If nodes are overloaded, consolidate to fewer nodes
                mode = ExecutionMode.PARALLEL_SAME_NODE
                logger.info("⚠️  Nodes overloaded, consolidating to parallel same node")
            else:
                # Use historical data if available
                if self._benchmarked:
                    multi_perf = self._get_avg_performance(ExecutionMode.PARALLEL_MULTI_NODE)
                    same_perf = self._get_avg_performance(ExecutionMode.PARALLEL_SAME_NODE)

                    if multi_perf and same_perf and multi_perf > same_perf * 1.1:
                        mode = ExecutionMode.PARALLEL_MULTI_NODE
                        logger.info("📡 Multi-node selected (benchmark proven)")
                    else:
                        mode = ExecutionMode.PARALLEL_SAME_NODE
                        logger.info("⚡ Parallel same node selected (faster per benchmark)")
                else:
                    mode = ExecutionMode.PARALLEL_MULTI_NODE
                    logger.info("📡 Multi-node selected (sufficient resources)")

        # 4. Limited nodes
        else:
            mode = self._choose_limited_node_mode(agent_count, len(healthy_nodes))

        logger.info(f"🎯 Final strategy: {mode.value}")
        return self._build_strategy(mode, agent_count)

    def _choose_single_node_mode(self, agent_count: int) -> ExecutionMode:
        """Choose best mode for single node execution with intelligence."""
        # If we have benchmark history, use it
        if self._benchmarked:
            single_perf = self._get_avg_performance(ExecutionMode.SINGLE_NODE)
            parallel_perf = self._get_avg_performance(ExecutionMode.PARALLEL_SAME_NODE)

            if parallel_perf and single_perf:
                # Choose based on throughput, but only if parallel is significantly better
                if parallel_perf > single_perf * 1.15:  # 15% threshold
                    logger.info(f"⚡ Parallel same node: {parallel_perf:.2f} vs {single_perf:.2f} agents/s")
                    return ExecutionMode.PARALLEL_SAME_NODE
                else:
                    logger.info(f"📍 Sequential: not enough benefit from parallel ({parallel_perf:.2f} vs {single_perf:.2f})")
                    return ExecutionMode.SINGLE_NODE

        # Heuristic: parallel for 3+ agents, single for fewer
        if agent_count >= 3:
            logger.info("⚡ Parallel same node (heuristic: 3+ agents)")
            return ExecutionMode.PARALLEL_SAME_NODE
        else:
            logger.info("📍 Sequential (heuristic: <3 agents)")
            return ExecutionMode.SINGLE_NODE

    def _choose_limited_node_mode(self, agent_count: int, node_count: int) -> ExecutionMode:
        """Choose mode when nodes < agents with intelligent decision."""
        ratio = node_count / agent_count

        # Check performance history
        if self._benchmarked:
            multi_perf = self._get_avg_performance(ExecutionMode.PARALLEL_MULTI_NODE)
            same_perf = self._get_avg_performance(ExecutionMode.PARALLEL_SAME_NODE)

            if multi_perf and same_perf:
                # If multi-node is faster even with limited nodes
                if multi_perf > same_perf * 1.1 and ratio >= 0.5:
                    logger.info(f"📡 Multi-node (limited): {node_count} nodes for {agent_count} agents")
                    return ExecutionMode.PARALLEL_MULTI_NODE
                else:
                    logger.info(f"⚡ Parallel same node: better performance with limited nodes")
                    return ExecutionMode.PARALLEL_SAME_NODE

        # Heuristic: if we have enough nodes for most agents, distribute
        if ratio >= 0.6:
            logger.info(f"📡 Multi-node: {node_count}/{agent_count} nodes available")
            return ExecutionMode.PARALLEL_MULTI_NODE

        # Otherwise, consolidate
        logger.info(f"⚡ Parallel same node: insufficient nodes ({node_count}/{agent_count})")
        return ExecutionMode.PARALLEL_SAME_NODE

    def _build_strategy(self, mode: ExecutionMode, agent_count: int) -> Dict:
        """Build strategy configuration."""
        strategy = {
            "mode": mode,
            "agent_count": agent_count,
            "routing_strategy": RoutingStrategy.LEAST_LOADED,
            "node_count": 1
        }

        if mode == ExecutionMode.SINGLE_NODE:
            strategy["node_count"] = 1
            strategy["routing_strategy"] = RoutingStrategy.LEAST_LOADED

        elif mode == ExecutionMode.PARALLEL_SAME_NODE:
            strategy["node_count"] = 1
            strategy["routing_strategy"] = RoutingStrategy.LEAST_LOADED

        elif mode == ExecutionMode.PARALLEL_MULTI_NODE:
            strategy["node_count"] = min(agent_count, len(self.registry.get_healthy_nodes()))
            strategy["routing_strategy"] = RoutingStrategy.LEAST_LOADED

        elif mode == ExecutionMode.GPU_ROUTING:
            gpu_count = len(self.registry.get_gpu_nodes())
            strategy["node_count"] = min(agent_count, gpu_count)
            strategy["routing_strategy"] = RoutingStrategy.GPU_FIRST

        return strategy

    def record_benchmark(self, mode: ExecutionMode, total_time: float,
                         agent_count: int, node_count: int, success: bool = True):
        """
        Record benchmark result and learn from performance.

        Args:
            mode: Execution mode used
            total_time: Total execution time
            agent_count: Number of agents executed
            node_count: Number of nodes used
            success: Whether execution succeeded
        """
        result = BenchmarkResult(
            mode=mode,
            total_time=total_time,
            avg_time_per_agent=total_time / agent_count if agent_count > 0 else 0,
            throughput=agent_count / total_time if total_time > 0 else 0,
            node_count=node_count,
            success=success
        )

        self.benchmark_history[mode].append(result)

        # Keep only last 20 results to adapt to changing conditions
        if len(self.benchmark_history[mode]) > 20:
            self.benchmark_history[mode].pop(0)

        self._benchmarked = True

        # Performance logging with learning indicators
        avg_perf = self._get_avg_performance(mode)
        trend = self._get_performance_trend(mode)

        logger.info(f"📊 Performance: {mode.value} - {total_time:.2f}s, "
                   f"{result.throughput:.2f} agents/s (avg: {avg_perf:.2f}, trend: {trend})")

        # Auto-adjust recommendations
        self._update_recommendations()

    def _get_performance_trend(self, mode: ExecutionMode) -> str:
        """Get performance trend (improving/stable/degrading)."""
        results = [r for r in self.benchmark_history[mode] if r.success]

        if len(results) < 3:
            return "insufficient data"

        # Compare recent vs older performance
        recent = results[-3:]
        older = results[-6:-3] if len(results) >= 6 else results[:-3]

        recent_avg = sum(r.throughput for r in recent) / len(recent)
        older_avg = sum(r.throughput for r in older) / len(older)

        if recent_avg > older_avg * 1.1:
            return "📈 improving"
        elif recent_avg < older_avg * 0.9:
            return "📉 degrading"
        else:
            return "➡️  stable"

    def _update_recommendations(self):
        """Update strategy recommendations based on all benchmark data."""
        if not self._benchmarked:
            return

        # Find best performing mode
        best_mode = None
        best_perf = 0

        for mode in ExecutionMode:
            perf = self._get_avg_performance(mode)
            if perf and perf > best_perf:
                best_perf = perf
                best_mode = mode

        if best_mode:
            logger.debug(f"💡 Current best strategy: {best_mode.value} ({best_perf:.2f} agents/s)")

    def _get_avg_performance(self, mode: ExecutionMode) -> Optional[float]:
        """Get average throughput for a mode."""
        results = [r for r in self.benchmark_history[mode] if r.success]

        if not results:
            return None

        return sum(r.throughput for r in results) / len(results)

    def run_auto_benchmark(self, test_agents: List, test_input: str, iterations: int = 3):
        """
        Run automatic benchmarking to find optimal strategy.

        Args:
            test_agents: List of agent instances to test with
            test_input: Test input for agents
            iterations: Number of iterations per mode
        """
        from concurrent.futures import ThreadPoolExecutor
        from load_balancer import OllamaLoadBalancer

        logger.info(f"🔬 Starting auto-benchmark ({iterations} iterations)")

        modes_to_test = [
            ExecutionMode.SINGLE_NODE,
            ExecutionMode.PARALLEL_SAME_NODE,
        ]

        # Add multi-node if available
        if len(self.registry.get_healthy_nodes()) >= len(test_agents):
            modes_to_test.append(ExecutionMode.PARALLEL_MULTI_NODE)

        # Add GPU if available
        if len(self.registry.get_gpu_nodes()) > 0:
            modes_to_test.append(ExecutionMode.GPU_ROUTING)

        lb = OllamaLoadBalancer(self.registry)

        for mode in modes_to_test:
            for i in range(iterations):
                logger.info(f"Testing {mode.value} (iteration {i+1}/{iterations})")

                try:
                    start = time.time()

                    if mode == ExecutionMode.SINGLE_NODE:
                        # Sequential on single node
                        node = lb.get_node()
                        for agent in test_agents:
                            agent.process(test_input)

                    elif mode == ExecutionMode.PARALLEL_SAME_NODE:
                        # Parallel on single node
                        node = lb.get_node()
                        with ThreadPoolExecutor(max_workers=len(test_agents)) as executor:
                            futures = [executor.submit(agent.process, test_input) for agent in test_agents]
                            for future in futures:
                                future.result()

                    elif mode == ExecutionMode.PARALLEL_MULTI_NODE:
                        # Parallel across multiple nodes
                        nodes = lb.get_nodes(len(test_agents))
                        with ThreadPoolExecutor(max_workers=len(test_agents)) as executor:
                            futures = [executor.submit(agent.process, test_input) for agent in test_agents]
                            for future in futures:
                                future.result()

                    elif mode == ExecutionMode.GPU_ROUTING:
                        # Route to GPU nodes
                        gpu_nodes = self.registry.get_gpu_nodes()
                        with ThreadPoolExecutor(max_workers=len(test_agents)) as executor:
                            futures = [executor.submit(agent.process, test_input) for agent in test_agents]
                            for future in futures:
                                future.result()

                    elapsed = time.time() - start
                    node_count = len(self.registry.get_healthy_nodes())

                    self.record_benchmark(mode, elapsed, len(test_agents), node_count, success=True)

                except Exception as e:
                    logger.error(f"Benchmark failed for {mode.value}: {e}")
                    self.record_benchmark(mode, 0, len(test_agents), 0, success=False)

        logger.info("✅ Auto-benchmark complete")
        self.print_benchmark_summary()

    def print_benchmark_summary(self):
        """Print summary of benchmark results."""
        print("\n" + "=" * 70)
        print(" BENCHMARK SUMMARY")
        print("=" * 70)

        for mode in ExecutionMode:
            results = [r for r in self.benchmark_history[mode] if r.success]

            if not results:
                continue

            avg_throughput = sum(r.throughput for r in results) / len(results)
            avg_time = sum(r.total_time for r in results) / len(results)

            print(f"\n{mode.value}:")
            print(f"  Avg Time: {avg_time:.2f}s")
            print(f"  Avg Throughput: {avg_throughput:.2f} agents/s")
            print(f"  Runs: {len(results)}")

        print("\n" + "=" * 70)

    def get_recommendations(self) -> Dict:
        """Get strategy recommendations based on benchmarks."""
        if not self._benchmarked:
            return {"error": "No benchmark data available"}

        best_mode = None
        best_throughput = 0

        for mode in ExecutionMode:
            perf = self._get_avg_performance(mode)
            if perf and perf > best_throughput:
                best_throughput = perf
                best_mode = mode

        return {
            "recommended_mode": best_mode.value if best_mode else None,
            "expected_throughput": best_throughput,
            "benchmarked": True
        }
