"""
Comprehensive benchmarking system for SynapticLlamas.
Compares different execution strategies, collaborative modes, and configurations.
"""

import time
import json
import logging
from typing import List, Dict
from dataclasses import dataclass, asdict
from datetime import datetime
from distributed_orchestrator import DistributedOrchestrator
from node_registry import NodeRegistry
from adaptive_strategy import ExecutionMode
from load_balancer import RoutingStrategy

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Results from a single benchmark run."""
    test_name: str
    mode: str
    strategy: str
    collaborative: bool
    ast_enabled: bool
    refinement_rounds: int
    query: str

    # Performance metrics
    total_time: float
    phase_times: List[tuple]

    # Quality metrics
    quality_score: float = 0.0
    quality_passed: bool = True

    # System metrics
    node_count: int = 1
    agent_count: int = 3

    # Result
    success: bool = True
    error: str = ""

    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class SynapticLlamasBenchmark:
    """Benchmark suite for testing different configurations."""

    def __init__(self, registry: NodeRegistry = None, model: str = "llama3.2"):
        self.registry = registry or NodeRegistry()
        self.model = model
        self.results: List[BenchmarkResult] = []

        # Ensure localhost is available
        if len(self.registry) == 0:
            self.registry.add_node("http://localhost:11434", name="localhost", priority=10)

    def run_full_benchmark(self, test_queries: List[str] = None) -> Dict:
        """Run comprehensive benchmark across all modes and strategies."""

        if not test_queries:
            test_queries = [
                "Explain how neural networks learn through backpropagation",
                "What are the key differences between TCP and UDP protocols?",
                "Describe the process of photosynthesis in detail"
            ]

        logger.info("🔬 Starting comprehensive benchmark suite")
        logger.info(f"📊 Testing {len(test_queries)} queries across multiple configurations")

        # Test configurations
        configs = [
            # Standard parallel mode
            {
                "name": "Parallel (No Collab)",
                "execution_mode": ExecutionMode.PARALLEL_SAME_NODE,
                "collaborative": False,
                "ast_enabled": False,
                "refinement_rounds": 0
            },
            # Collaborative mode
            {
                "name": "Collaborative (No AST)",
                "execution_mode": None,
                "collaborative": True,
                "ast_enabled": False,
                "refinement_rounds": 1
            },
            # Collaborative + AST
            {
                "name": "Collaborative + AST (0.7)",
                "execution_mode": None,
                "collaborative": True,
                "ast_enabled": True,
                "refinement_rounds": 1
            },
            # High quality mode
            {
                "name": "High Quality (AST 0.9)",
                "execution_mode": None,
                "collaborative": True,
                "ast_enabled": True,
                "refinement_rounds": 2
            }
        ]

        # Run benchmarks
        orchestrator = DistributedOrchestrator(self.registry)

        for query in test_queries:
            logger.info(f"\n📝 Testing query: {query[:60]}...")

            for config in configs:
                logger.info(f"⚙️  Config: {config['name']}")

                result = self._run_single_benchmark(
                    orchestrator,
                    query,
                    config
                )
                self.results.append(result)

                # Brief pause between runs
                time.sleep(2)

        # Generate report
        return self._generate_report()

    def _run_single_benchmark(self, orchestrator: DistributedOrchestrator,
                             query: str, config: Dict) -> BenchmarkResult:
        """Run a single benchmark configuration."""

        start_time = time.time()

        try:
            result = orchestrator.run(
                query,
                model=self.model,
                execution_mode=config.get('execution_mode'),
                collaborative=config['collaborative'],
                refinement_rounds=config['refinement_rounds'],
                enable_ast_voting=config['ast_enabled'],
                quality_threshold=0.9 if "0.9" in config['name'] else 0.7,
                max_quality_retries=2
            )

            total_time = time.time() - start_time

            # Extract metrics
            phase_times = result['metrics'].get('phase_timings', [])
            quality_scores = result['metrics'].get('quality_scores', [])
            quality_passed = result['metrics'].get('quality_passed', True)

            avg_quality = 0.0
            if quality_scores:
                avg_quality = sum(s['score'] for s in quality_scores) / len(quality_scores)

            return BenchmarkResult(
                test_name=config['name'],
                mode="collaborative" if config['collaborative'] else "parallel",
                strategy=str(config.get('execution_mode', 'auto')),
                collaborative=config['collaborative'],
                ast_enabled=config['ast_enabled'],
                refinement_rounds=config['refinement_rounds'],
                query=query[:100],
                total_time=total_time,
                phase_times=phase_times,
                quality_score=avg_quality,
                quality_passed=quality_passed,
                node_count=len(self.registry),
                success=True
            )

        except Exception as e:
            logger.error(f"❌ Benchmark failed: {e}")
            return BenchmarkResult(
                test_name=config['name'],
                mode="collaborative" if config['collaborative'] else "parallel",
                strategy=str(config.get('execution_mode', 'auto')),
                collaborative=config['collaborative'],
                ast_enabled=config['ast_enabled'],
                refinement_rounds=config['refinement_rounds'],
                query=query[:100],
                total_time=time.time() - start_time,
                phase_times=[],
                success=False,
                error=str(e)
            )

    def _generate_report(self) -> Dict:
        """Generate comprehensive benchmark report."""

        # Group by configuration
        by_config = {}
        for result in self.results:
            if result.test_name not in by_config:
                by_config[result.test_name] = []
            by_config[result.test_name].append(result)

        # Calculate statistics
        summary = {
            "total_tests": len(self.results),
            "successful_tests": sum(1 for r in self.results if r.success),
            "failed_tests": sum(1 for r in self.results if not r.success),
            "configurations_tested": len(by_config),
            "test_timestamp": datetime.now().isoformat()
        }

        # Configuration performance
        config_stats = {}
        for config_name, results in by_config.items():
            successful = [r for r in results if r.success]

            if successful:
                avg_time = sum(r.total_time for r in successful) / len(successful)
                avg_quality = sum(r.quality_score for r in successful) / len(successful) if successful[0].ast_enabled else 0.0

                config_stats[config_name] = {
                    "avg_time": round(avg_time, 2),
                    "min_time": round(min(r.total_time for r in successful), 2),
                    "max_time": round(max(r.total_time for r in successful), 2),
                    "avg_quality_score": round(avg_quality, 2),
                    "success_rate": len(successful) / len(results) * 100
                }

        # Recommendations
        recommendations = self._generate_recommendations(config_stats)

        report = {
            "summary": summary,
            "configuration_performance": config_stats,
            "recommendations": recommendations,
            "detailed_results": [asdict(r) for r in self.results]
        }

        return report

    def _generate_recommendations(self, config_stats: Dict) -> List[str]:
        """Generate recommendations based on benchmark results."""
        recommendations = []

        if config_stats:
            # Find fastest
            fastest = min(config_stats.items(), key=lambda x: x[1]['avg_time'])
            recommendations.append(
                f"⚡ Fastest: '{fastest[0]}' with {fastest[1]['avg_time']}s average"
            )

            # Find highest quality
            highest_quality = max(
                [(k, v) for k, v in config_stats.items() if v['avg_quality_score'] > 0],
                key=lambda x: x[1]['avg_quality_score'],
                default=None
            )

            if highest_quality:
                recommendations.append(
                    f"🏆 Highest Quality: '{highest_quality[0]}' with {highest_quality[1]['avg_quality_score']} score"
                )

            # Balance recommendation
            recommendations.append(
                "⚖️  Recommended: 'Collaborative + AST (0.7)' for balanced speed and quality"
            )

        return recommendations

    def save_results(self, filename: str = "benchmark_results.json"):
        """Save benchmark results to file."""
        report = self._generate_report()

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"📊 Benchmark results saved to {filename}")
        return filename

    def print_summary(self):
        """Print benchmark summary to console."""
        report = self._generate_report()

        print("\n" + "="*70)
        print("📊 SYNAPTICLLAMAS BENCHMARK RESULTS")
        print("="*70)

        print(f"\n📈 Summary:")
        print(f"  Total Tests: {report['summary']['total_tests']}")
        print(f"  Successful: {report['summary']['successful_tests']}")
        print(f"  Failed: {report['summary']['failed_tests']}")

        print(f"\n⚙️  Configuration Performance:")
        for config, stats in report['configuration_performance'].items():
            print(f"\n  {config}:")
            print(f"    Avg Time: {stats['avg_time']}s")
            print(f"    Range: {stats['min_time']}s - {stats['max_time']}s")
            if stats['avg_quality_score'] > 0:
                print(f"    Avg Quality: {stats['avg_quality_score']}")
            print(f"    Success Rate: {stats['success_rate']:.1f}%")

        print(f"\n💡 Recommendations:")
        for rec in report['recommendations']:
            print(f"  {rec}")

        print("\n" + "="*70 + "\n")


def main():
    """Run benchmarks from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="SynapticLlamas Benchmark Suite")
    parser.add_argument("--model", default="llama3.2", help="Ollama model to use")
    parser.add_argument("--output", default="benchmark_results.json", help="Output file")
    parser.add_argument("--queries", nargs="+", help="Custom test queries")

    args = parser.parse_args()

    benchmark = SynapticLlamasBenchmark(model=args.model)
    benchmark.run_full_benchmark(test_queries=args.queries)
    benchmark.print_summary()
    benchmark.save_results(args.output)


if __name__ == "__main__":
    main()
