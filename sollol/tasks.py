"""
Task and Result Abstractions for Distributed Execution

Provides standard task and result dataclasses for SOLLOL distributed execution.
These abstractions enable consistent task submission, execution tracking, and
result collection across different execution strategies.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class DistributedTask:
    """
    Represents a single task to be executed in a distributed system.

    This abstraction provides a standard contract for submitting work
    to SOLLOL's distributed execution engine.

    Attributes:
        task_id: Unique identifier for the task
        payload: Task payload (prompts, messages, data, etc.)
        priority: Task priority (1-10, higher = more important)
        timeout: Maximum execution time in seconds
        metadata: Additional task metadata
    """
    task_id: str
    payload: Dict[str, Any]
    priority: int = 5
    timeout: float = 300.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate task parameters."""
        if not 1 <= self.priority <= 10:
            raise ValueError(f"Priority must be 1-10, got {self.priority}")
        if self.timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {self.timeout}")


@dataclass
class TaskResult:
    """
    Result from executing a distributed task.

    Contains execution metadata, results, and performance information
    for adaptive learning and result aggregation.

    Attributes:
        task_id: ID of the task that was executed
        node_url: URL of the node that executed the task
        result: Task execution result (any type)
        duration_ms: Actual execution duration in milliseconds
        success: Whether the task completed successfully
        error: Error message if task failed
        routing_metadata: Metadata from SOLLOL routing decision
        timestamp: When the task completed
    """
    task_id: str
    node_url: str
    result: Any
    duration_ms: float
    success: bool
    error: Optional[str] = None
    routing_metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionResult:
    """
    Aggregated result from parallel execution of multiple tasks.

    Contains merged results, individual task results, and comprehensive
    execution statistics for monitoring and optimization.

    Attributes:
        merged_result: Aggregated result based on merge strategy
        individual_results: List of individual TaskResult objects
        statistics: Execution statistics (timing, success rate, etc.)
        execution_mode: Mode used for execution (parallel, sequential, etc.)
    """
    merged_result: Any
    individual_results: list[TaskResult]
    statistics: Dict[str, Any]
    execution_mode: str

    @property
    def success_rate(self) -> float:
        """Calculate success rate of execution."""
        if not self.individual_results:
            return 0.0
        successful = sum(1 for r in self.individual_results if r.success)
        return successful / len(self.individual_results)

    @property
    def total_duration_ms(self) -> float:
        """Get total execution duration (wall clock time)."""
        return self.statistics.get('total_duration_ms', 0.0)

    @property
    def avg_task_duration_ms(self) -> float:
        """Get average task duration."""
        return self.statistics.get('avg_task_duration_ms', 0.0)

    @property
    def speedup_factor(self) -> float:
        """Get speedup factor vs sequential execution."""
        return self.statistics.get('speedup_factor', 1.0)
