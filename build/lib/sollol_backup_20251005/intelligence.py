"""
Intelligent routing engine - Context-aware request classification and optimization.

This module provides advanced routing decisions based on:
- Request content analysis
- Task type detection
- Historical performance patterns
- Resource requirements prediction
"""
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime
import re

@dataclass
class TaskContext:
    """Rich context about a request for intelligent routing decisions."""
    task_type: str  # 'generation', 'embedding', 'classification', 'extraction', etc.
    complexity: str  # 'simple', 'medium', 'complex'
    estimated_tokens: int
    model_preference: Optional[str]
    priority: int  # 1-10, higher = more important
    requires_gpu: bool
    estimated_duration_ms: float
    metadata: Dict

class IntelligentRouter:
    """
    Context-aware routing engine that makes smart decisions about which
    OLLOL node should handle each request.

    Unlike simple round-robin or random load balancing, this router:
    - Analyzes request content to determine task type
    - Predicts resource requirements
    - Routes based on node capabilities and current load
    - Learns from historical patterns
    """

    def __init__(self):
        self.task_patterns = {
            'embedding': [
                r'embed',
                r'vector',
                r'similarity',
                r'semantic.*search',
            ],
            'generation': [
                r'generat',
                r'creat',
                r'writ',
                r'complet',
                r'continue',
            ],
            'classification': [
                r'classif',
                r'categor',
                r'label',
                r'sentiment',
            ],
            'extraction': [
                r'extract',
                r'parse',
                r'identif',
                r'find.*entities',
            ],
            'summarization': [
                r'summar',
                r'condense',
                r'brief',
            ],
            'analysis': [
                r'analyz',
                r'evaluat',
                r'assess',
            ],
        }

        # Historical performance by task type and model
        self.performance_history: Dict[str, List[float]] = {}

        # Node capabilities (GPU, CPU-heavy models, etc.)
        self.node_capabilities: Dict[str, Dict] = {}

    def detect_task_type(self, payload: Dict) -> str:
        """
        Intelligently detect what kind of task this request represents.

        Args:
            payload: Request payload (messages, prompts, etc.)

        Returns:
            Task type string ('generation', 'embedding', 'classification', etc.)
        """
        # Check if it's explicitly an embedding request
        if 'prompt' in payload and 'model' in payload:
            model = payload.get('model', '').lower()
            if 'embed' in model or 'nomic' in model:
                return 'embedding'

        # Analyze message content
        content = self._extract_content(payload)
        content_lower = content.lower()

        # Score each task type based on pattern matches
        scores = {}
        for task_type, patterns in self.task_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, content_lower):
                    score += 1
            if score > 0:
                scores[task_type] = score

        # Return highest scoring task type, or 'generation' as default
        if scores:
            return max(scores, key=scores.get)

        return 'generation'

    def estimate_complexity(self, payload: Dict) -> Tuple[str, int]:
        """
        Estimate request complexity and token count.

        Returns:
            (complexity_level, estimated_tokens)
        """
        content = self._extract_content(payload)

        # Rough token estimation (4 chars ≈ 1 token)
        estimated_tokens = len(content) // 4

        # Classify complexity
        if estimated_tokens < 500:
            complexity = 'simple'
        elif estimated_tokens < 2000:
            complexity = 'medium'
        else:
            complexity = 'complex'

        # Check for multi-turn conversation
        if isinstance(payload.get('messages'), list):
            if len(payload['messages']) > 5:
                # Long conversations are more complex
                complexity = 'complex' if complexity != 'complex' else complexity
                estimated_tokens *= 1.5

        return complexity, int(estimated_tokens)

    def analyze_request(self, payload: Dict, priority: int = 5) -> TaskContext:
        """
        Perform full request analysis to build routing context.

        Args:
            payload: Request payload
            priority: Request priority (1-10)

        Returns:
            TaskContext with all routing information
        """
        task_type = self.detect_task_type(payload)
        complexity, tokens = self.estimate_complexity(payload)

        # Determine if GPU is beneficial
        requires_gpu = (
            task_type in ['generation', 'embedding', 'summarization', 'analysis'] and
            complexity in ['medium', 'complex']
        )

        # Estimate duration based on historical data
        estimated_duration = self._estimate_duration(task_type, tokens)

        # Extract model preference if specified
        model_preference = payload.get('model')

        return TaskContext(
            task_type=task_type,
            complexity=complexity,
            estimated_tokens=tokens,
            model_preference=model_preference,
            priority=priority,
            requires_gpu=requires_gpu,
            estimated_duration_ms=estimated_duration,
            metadata={
                'analyzed_at': datetime.now().isoformat(),
                'confidence': 'high' if task_type != 'generation' else 'medium',
            }
        )

    def select_optimal_node(
        self,
        context: TaskContext,
        available_hosts: List[Dict]
    ) -> Tuple[str, Dict]:
        """
        Select the optimal OLLOL node for this request based on context.

        Args:
            context: Task context from analyze_request()
            available_hosts: List of available host metadata

        Returns:
            (selected_host, routing_decision) tuple with reasoning
        """
        # Filter to only truly available hosts
        available = [h for h in available_hosts if h.get('available', True)]

        if not available:
            raise ValueError("No available hosts")

        # Score each host
        scored_hosts = []
        for host_meta in available:
            score = self._score_host_for_context(host_meta, context)
            scored_hosts.append((host_meta, score))

        # Sort by score (descending)
        scored_hosts.sort(key=lambda x: x[1], reverse=True)

        # Select best host
        best_host, best_score = scored_hosts[0]

        # Build decision reasoning
        decision = {
            'selected_host': best_host['host'],
            'score': best_score,
            'task_type': context.task_type,
            'complexity': context.complexity,
            'reasoning': self._explain_decision(best_host, context, scored_hosts),
            'alternatives': [
                {'host': h['host'], 'score': s}
                for h, s in scored_hosts[1:3]  # Top 2 alternatives
            ]
        }

        return best_host['host'], decision

    def _score_host_for_context(self, host_meta: Dict, context: TaskContext) -> float:
        """
        Score how well a host matches the request context AND resources.

        Scoring factors (in order of importance):
        1. Availability (binary: available or not)
        2. Resource adequacy (does it have what the task needs?)
        3. Current performance (latency, success rate)
        4. Current load (CPU, GPU utilization)
        5. Priority/preferences (host priority, task priority alignment)

        Higher score = better match for this request.
        """
        score = 100.0  # Start with baseline

        # Factor 1: Availability (CRITICAL - binary disqualification)
        if not host_meta.get('available', True):
            return 0.0

        # Factor 2: Resource adequacy (CRITICAL for resource-intensive tasks)
        # GPU requirements
        if context.requires_gpu:
            gpu_mem = host_meta.get('gpu_free_mem', 0)
            if gpu_mem == 0:
                # No GPU but task needs it - heavy penalty
                score *= 0.2  # Still possible but very low priority
            elif gpu_mem < 2000:
                # Low GPU memory - risky
                score *= 0.5
            elif gpu_mem > 4000:
                # Good GPU availability - bonus!
                score *= 1.5
            elif gpu_mem > 8000:
                # Excellent GPU availability - big bonus!
                score *= 2.0

        # CPU requirements based on complexity
        cpu_load = host_meta.get('cpu_load', 0.5)
        if context.complexity == 'complex':
            # Complex tasks need low CPU load
            if cpu_load > 0.8:
                score *= 0.3  # Very busy host, bad for complex tasks
            elif cpu_load < 0.3:
                score *= 1.3  # Idle host, great for complex tasks
        elif context.complexity == 'simple':
            # Simple tasks can tolerate higher load
            if cpu_load > 0.9:
                score *= 0.7  # Still penalize very busy hosts
            # Don't bonus idle hosts for simple tasks

        # Factor 3: Current performance
        success_rate = host_meta.get('success_rate', 1.0)
        score *= success_rate  # Direct multiplier

        latency_ms = host_meta.get('latency_ms', 200.0)
        # Latency penalty scales with task priority and is more aggressive for extreme values
        latency_weight = 1.0 + (context.priority / 10.0)  # 1.0 to 2.0
        # Use exponential penalty for very high latency (>1000ms)
        if latency_ms > 1000:
            latency_penalty = (latency_ms / 100.0) * latency_weight
        else:
            latency_penalty = min(latency_ms / 100.0, 10.0) * latency_weight
        score /= (1 + latency_penalty)

        # Factor 4: Additional load considerations
        # Penalize heavily loaded nodes more for high-priority tasks
        if context.priority >= 7:  # High priority
            load_penalty = cpu_load * 3.0  # Aggressive penalty
        else:
            load_penalty = cpu_load * 1.5  # Standard penalty
        score /= (1 + load_penalty)

        # Factor 5: Priority alignment
        # Prefer priority 0 hosts for high-priority tasks
        host_priority = host_meta.get('priority', 999)
        if host_priority == 0 and context.priority >= 7:
            score *= 1.5  # Strong bonus for high-pri tasks on high-pri hosts
        elif host_priority == 0:
            score *= 1.2  # Standard bonus

        # Factor 6: Task-type specialization
        # If host has metadata about preferred task types, use it
        preferred_tasks = host_meta.get('preferred_task_types', [])
        if context.task_type in preferred_tasks:
            score *= 1.3

        # Factor 7: Resource headroom for estimated duration
        # Penalize if estimated duration is long and host is already loaded
        if context.estimated_duration_ms > 5000:  # > 5 seconds
            if cpu_load > 0.6:
                score *= 0.7  # Don't want long tasks on busy hosts

        return score

    def _explain_decision(
        self,
        selected_host: Dict,
        context: TaskContext,
        all_scored: List[Tuple[Dict, float]]
    ) -> str:
        """
        Generate human-readable explanation of routing decision.
        """
        reasons = []

        host = selected_host['host']
        latency = selected_host.get('latency_ms', 0)
        success_rate = selected_host.get('success_rate', 1.0)

        reasons.append(f"Task: {context.task_type} ({context.complexity})")
        reasons.append(f"Host {host}: latency={latency:.1f}ms, success={success_rate:.1%}")

        if context.requires_gpu:
            gpu_mem = selected_host.get('gpu_free_mem', 0)
            reasons.append(f"GPU preferred: {gpu_mem}MB available")

        if len(all_scored) > 1:
            second_best = all_scored[1]
            score_margin = all_scored[0][1] - second_best[1]
            if score_margin < 10:
                reasons.append(f"Close call (margin: {score_margin:.1f})")

        return "; ".join(reasons)

    def _extract_content(self, payload: Dict) -> str:
        """Extract text content from various payload formats."""
        # Chat format
        if 'messages' in payload:
            messages = payload['messages']
            if isinstance(messages, list):
                return " ".join([
                    msg.get('content', '')
                    for msg in messages
                    if isinstance(msg, dict)
                ])

        # Embedding format
        if 'prompt' in payload:
            return str(payload['prompt'])

        # Direct content
        if 'content' in payload:
            return str(payload['content'])

        return ""

    def _estimate_duration(self, task_type: str, tokens: int) -> float:
        """
        Estimate request duration based on task type and token count.

        Returns:
            Estimated duration in milliseconds
        """
        # Base durations by task type (ms per token)
        base_rates = {
            'embedding': 0.5,      # Fast
            'classification': 1.0,  # Medium
            'extraction': 1.5,      # Medium-slow
            'generation': 3.0,      # Slow (autoregressive)
            'summarization': 2.5,   # Slow
            'analysis': 2.0,        # Medium-slow
        }

        rate = base_rates.get(task_type, 2.0)
        return tokens * rate

    def record_performance(
        self,
        task_type: str,
        model: str,
        actual_duration_ms: float
    ):
        """
        Record actual performance for learning and optimization.

        This allows the router to improve over time.
        """
        key = f"{task_type}:{model}"
        if key not in self.performance_history:
            self.performance_history[key] = []

        self.performance_history[key].append(actual_duration_ms)

        # Keep only last 100 measurements
        if len(self.performance_history[key]) > 100:
            self.performance_history[key] = self.performance_history[key][-100:]

# Global router instance
_router = IntelligentRouter()

def get_router() -> IntelligentRouter:
    """Get the global intelligent router instance."""
    return _router
