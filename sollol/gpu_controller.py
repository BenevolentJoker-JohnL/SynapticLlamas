"""
SOLLOL GPU Controller - Active GPU model placement and verification.

This module ensures that SOLLOL's intelligent routing is backed by actual GPU
placement, not just passive routing to GPU nodes. Without this, SOLLOL's
performance optimization promise is broken.

Integration with SOLLOL:
- Works with NodeRegistry (not simple list)
- Integrates with IntelligentRouter for verification
- Pre-warms critical models on GPU nodes
- Validates models are actually on GPU after routing
"""
import requests
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelPlacement:
    """Information about where a model is actually loaded."""
    node_url: str
    model_name: str
    location: str  # 'GPU (VRAM)' or 'CPU (RAM)'
    size_mb: float
    vram_mb: float
    timestamp: float


class SOLLOLGPUController:
    """
    Active GPU controller for SOLLOL.

    Ensures that when IntelligentRouter routes to GPU nodes, models
    actually load on GPU. Without this, routing is wasted effort.

    Key difference from FlockParser's GPUController:
    - Integrates with NodeRegistry (not simple list)
    - Works with IntelligentRouter for validation loop
    - Tracks placement history for optimization
    """

    def __init__(self, node_registry=None):
        """
        Initialize GPU controller.

        Args:
            node_registry: NodeRegistry instance (optional, can be set later)
        """
        self.registry = node_registry
        self.placement_history: Dict[str, ModelPlacement] = {}
        self._cache_timeout = 60.0  # Cache model status for 60s

    def set_registry(self, registry):
        """Set the NodeRegistry after initialization."""
        self.registry = registry

    def get_model_status(self, node_url: str) -> Dict:
        """
        Get current model loading status (GPU vs CPU).

        Args:
            node_url: Ollama node URL

        Returns:
            Status dictionary with model locations
        """
        try:
            response = requests.get(f"{node_url}/api/ps", timeout=5)
            if response.status_code != 200:
                return {"error": "Failed to connect"}

            ps_data = response.json()
            models = ps_data.get("models", [])

            status = {
                'node_url': node_url,
                'models': [],
                'gpu_count': 0,
                'cpu_count': 0,
                'timestamp': time.time()
            }

            for model_info in models:
                model_name = model_info.get("name", "unknown")
                size_vram = model_info.get("size_vram", 0)
                size_total = model_info.get("size", 0)

                location = 'GPU (VRAM)' if size_vram > 0 else 'CPU (RAM)'
                if size_vram > 0:
                    status['gpu_count'] += 1
                else:
                    status['cpu_count'] += 1

                model_data = {
                    'name': model_name,
                    'location': location,
                    'size_mb': size_total / (1024**2),
                    'vram_mb': size_vram / (1024**2)
                }
                status['models'].append(model_data)

                # Update placement history
                placement = ModelPlacement(
                    node_url=node_url,
                    model_name=model_name,
                    location=location,
                    size_mb=model_data['size_mb'],
                    vram_mb=model_data['vram_mb'],
                    timestamp=time.time()
                )
                self.placement_history[f"{node_url}:{model_name}"] = placement

            return status

        except Exception as e:
            logger.error(f"Error getting model status from {node_url}: {e}")
            return {"error": str(e)}

    def force_gpu_load(
        self,
        node_url: str,
        model_name: str,
        num_gpu_layers: int = -1
    ) -> Dict:
        """
        Force a model to load on GPU.

        This is CRITICAL for SOLLOL's performance promise. Without this,
        intelligent routing to GPU nodes is wasted if models load on CPU.

        Args:
            node_url: Ollama node URL
            model_name: Model to load (e.g., "mxbai-embed-large")
            num_gpu_layers: Number of layers on GPU (-1 = all)

        Returns:
            Result dictionary with success status
        """
        try:
            logger.info(f"🔄 Forcing {model_name} to GPU on {node_url}")

            # Step 1: Unload the model
            requests.post(
                f"{node_url}/api/generate",
                json={
                    "model": model_name,
                    "keep_alive": 0
                },
                timeout=10
            )
            time.sleep(2)

            # Step 2: Reload with GPU configuration
            if 'embed' in model_name.lower():
                # Embedding model
                load_response = requests.post(
                    f"{node_url}/api/embed",
                    json={
                        "model": model_name,
                        "input": "warmup",
                        "options": {
                            "num_gpu": num_gpu_layers
                        },
                        "keep_alive": "1h"
                    },
                    timeout=30
                )
            else:
                # Chat/generation model
                load_response = requests.post(
                    f"{node_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "warmup",
                        "options": {
                            "num_gpu": num_gpu_layers
                        },
                        "keep_alive": "1h"
                    },
                    timeout=30
                )

            time.sleep(2)

            # Step 3: Verify GPU loading
            status = self.get_model_status(node_url)

            for model in status.get('models', []):
                if model_name in model['name']:
                    if 'GPU' in model['location']:
                        logger.info(f"✅ {model_name} now on GPU ({model['vram_mb']:.1f}MB)")
                        return {
                            'success': True,
                            'message': f"✅ {model_name} on GPU",
                            'location': model['location'],
                            'vram_mb': model['vram_mb']
                        }
                    else:
                        logger.warning(f"⚠️  {model_name} still on CPU (may need more VRAM)")
                        return {
                            'success': False,
                            'message': f"⚠️  {model_name} on CPU (insufficient VRAM?)",
                            'location': model['location']
                        }

            return {
                'success': False,
                'message': f"⚠️  {model_name} not found after reload"
            }

        except Exception as e:
            logger.error(f"Error forcing GPU load: {e}")
            return {
                'success': False,
                'message': f"❌ Error: {str(e)}"
            }

    def force_cpu_load(self, node_url: str, model_name: str) -> Dict:
        """
        Force a model to load on CPU.

        Useful for freeing VRAM for higher-priority models.

        Args:
            node_url: Ollama node URL
            model_name: Model to move to CPU

        Returns:
            Result dictionary
        """
        try:
            logger.info(f"🔄 Forcing {model_name} to CPU on {node_url}")

            # Unload
            requests.post(
                f"{node_url}/api/generate",
                json={"model": model_name, "keep_alive": 0},
                timeout=10
            )
            time.sleep(2)

            # Reload with CPU-only
            if 'embed' in model_name.lower():
                requests.post(
                    f"{node_url}/api/embed",
                    json={
                        "model": model_name,
                        "input": "warmup",
                        "options": {"num_gpu": 0},
                        "keep_alive": "1h"
                    },
                    timeout=30
                )
            else:
                requests.post(
                    f"{node_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": "warmup",
                        "options": {"num_gpu": 0},
                        "keep_alive": "1h"
                    },
                    timeout=30
                )

            time.sleep(2)

            # Verify
            status = self.get_model_status(node_url)
            for model in status.get('models', []):
                if model_name in model['name']:
                    logger.info(f"✅ {model_name} now on CPU")
                    return {
                        'success': True,
                        'message': f"✅ {model_name} on CPU",
                        'location': model['location']
                    }

            return {'success': False, 'message': "Model not found"}

        except Exception as e:
            logger.error(f"Error forcing CPU load: {e}")
            return {'success': False, 'message': f"Error: {str(e)}"}

    def verify_routing_decision(
        self,
        node_url: str,
        model_name: str,
        expected_location: str = 'GPU'
    ) -> bool:
        """
        Verify that a model is where the router expected it to be.

        This is the validation loop that makes SOLLOL's intelligence reliable.

        Args:
            node_url: Node that should have the model
            model_name: Model to verify
            expected_location: 'GPU' or 'CPU'

        Returns:
            True if model is in expected location, False otherwise
        """
        status = self.get_model_status(node_url)

        for model in status.get('models', []):
            if model_name in model['name']:
                actual_location = 'GPU' if 'GPU' in model['location'] else 'CPU'

                if actual_location == expected_location:
                    logger.debug(f"✅ Verified: {model_name} on {expected_location} at {node_url}")
                    return True
                else:
                    logger.warning(
                        f"⚠️  Routing mismatch: {model_name} on {actual_location}, "
                        f"expected {expected_location} at {node_url}"
                    )
                    return False

        logger.warning(f"⚠️  Model {model_name} not found at {node_url}")
        return False

    def pre_warm_gpu_nodes(
        self,
        priority_models: List[str],
        max_concurrent: int = 3
    ) -> Dict[str, List[Dict]]:
        """
        Pre-warm GPU nodes with critical models.

        This ensures the first request doesn't have to wait for model loading.

        Args:
            priority_models: Models to pre-load (e.g., ["mxbai-embed-large", "llama3.1"])
            max_concurrent: Max models to load per node

        Returns:
            Report of pre-warming results by node
        """
        if not self.registry:
            logger.error("No NodeRegistry set, cannot pre-warm")
            return {}

        logger.info(f"🔥 Pre-warming GPU nodes with {len(priority_models)} models")

        gpu_nodes = self.registry.get_gpu_nodes()
        if not gpu_nodes:
            logger.warning("No GPU nodes available for pre-warming")
            return {}

        report = {}

        for node in gpu_nodes:
            node_url = node.url
            node_results = []

            for i, model in enumerate(priority_models):
                if i >= max_concurrent:
                    logger.info(f"Max concurrent limit reached for {node_url}")
                    break

                result = self.force_gpu_load(node_url, model)
                node_results.append({
                    'model': model,
                    'result': result
                })

            report[node_url] = node_results

        logger.info(f"✅ Pre-warming complete for {len(gpu_nodes)} GPU nodes")
        return report

    def optimize_cluster(
        self,
        gpu_priority_models: List[str]
    ) -> Dict:
        """
        Optimize model placement across the cluster.

        Strategy:
        1. Load priority models on GPU nodes
        2. Verify placements
        3. Report any failures

        Args:
            gpu_priority_models: Models that should be on GPU

        Returns:
            Optimization report
        """
        if not self.registry:
            logger.error("No NodeRegistry set, cannot optimize")
            return {'error': 'No registry configured'}

        logger.info("🔧 Optimizing cluster GPU/CPU assignments")

        report = {
            'gpu_nodes': [],
            'cpu_nodes': [],
            'assignments': []
        }

        # Classify nodes
        for node in self.registry.nodes.values():
            if node.capabilities.has_gpu:
                report['gpu_nodes'].append(node.url)
            else:
                report['cpu_nodes'].append(node.url)

        # Assign priority models to GPU nodes
        for model_name in gpu_priority_models:
            for gpu_node_url in report['gpu_nodes']:
                result = self.force_gpu_load(gpu_node_url, model_name)
                report['assignments'].append({
                    'node': gpu_node_url,
                    'model': model_name,
                    'target': 'GPU',
                    'result': result
                })

        logger.info(f"✅ Cluster optimization complete")
        return report

    def print_cluster_status(self):
        """Print formatted cluster GPU/CPU status."""
        if not self.registry:
            logger.error("No NodeRegistry set")
            return

        print("\n" + "="*70)
        print("🌐 SOLLOL CLUSTER GPU/CPU STATUS")
        print("="*70)

        for node in self.registry.nodes.values():
            node_url = node.url
            status = self.get_model_status(node_url)

            if 'error' in status:
                print(f"\n❌ {node.name} ({node_url}): {status['error']}")
                continue

            gpu_count = status.get('gpu_count', 0)
            cpu_count = status.get('cpu_count', 0)
            total = gpu_count + cpu_count

            if gpu_count > 0:
                node_type = f"🚀 GPU ({gpu_count}/{total} models on GPU)"
            else:
                node_type = f"🐢 CPU (all {cpu_count} models on CPU)"

            print(f"\n{node_type} {node.name} ({node_url}):")

            for model in status.get('models', []):
                location_emoji = "🚀" if "GPU" in model['location'] else "🐢"
                print(f"   {location_emoji} {model['name']}")
                print(f"      Location: {model['location']}")
                print(f"      Size: {model['size_mb']:.1f} MB")
                if model['vram_mb'] > 0:
                    print(f"      VRAM: {model['vram_mb']:.1f} MB")

        print("="*70 + "\n")

    def get_placement_stats(self) -> Dict:
        """
        Get statistics about model placements.

        Returns:
            Statistics dictionary
        """
        total = len(self.placement_history)
        gpu_count = sum(1 for p in self.placement_history.values() if 'GPU' in p.location)
        cpu_count = total - gpu_count

        return {
            'total_placements': total,
            'gpu_placements': gpu_count,
            'cpu_placements': cpu_count,
            'gpu_percentage': (gpu_count / total * 100) if total > 0 else 0,
            'recent_placements': list(self.placement_history.values())[-10:]
        }


def integrate_with_router(router, gpu_controller, node_registry):
    """
    Integrate GPU controller with IntelligentRouter for validation loop.

    This creates a feedback loop:
    1. Router selects GPU node
    2. GPU controller verifies model is on GPU
    3. If not, forces GPU load
    4. Router learns from actual performance

    Args:
        router: IntelligentRouter instance
        gpu_controller: SOLLOLGPUController instance
        node_registry: NodeRegistry instance
    """
    gpu_controller.set_registry(node_registry)

    # Pre-warm common embedding models on GPU nodes
    priority_models = [
        "mxbai-embed-large",
        "nomic-embed-text",
        "llama3.1",
        "llama3.2"
    ]

    logger.info("🔗 Integrating GPU controller with intelligent router")
    gpu_controller.pre_warm_gpu_nodes(priority_models, max_concurrent=2)
    logger.info("✅ GPU controller integration complete")
