"""
Task prioritization and queue management.

Ensures high-priority requests get processed first while maintaining
fairness and preventing starvation of lower-priority tasks.
"""
import asyncio
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import heapq

@dataclass
class PrioritizedTask:
    """
    A task with priority for queue management.

    Tasks are ordered by:
    1. Priority (higher first)
    2. Age (older first, prevents starvation)
    """
    priority: int
    timestamp: float
    task_id: str
    payload: Dict
    future: asyncio.Future

    def __lt__(self, other):
        # Higher priority goes first (inverted for min-heap)
        if self.priority != other.priority:
            return self.priority > other.priority
        # If same priority, older tasks go first (FIFO within priority)
        return self.timestamp < other.timestamp

class PriorityQueue:
    """
    Priority queue for SOLLOL requests.

    Features:
    - Priority-based ordering (1-10, 10 = highest)
    - Age-based fairness (prevents starvation)
    - Async-friendly
    - Metrics tracking
    """

    def __init__(self, max_queue_size: int = 1000):
        self.queue = []
        self.max_size = max_queue_size
        self.lock = asyncio.Lock()

        # Metrics
        self.total_queued = 0
        self.total_processed = 0
        self.queue_wait_times: Dict[int, list] = {}  # priority -> wait times

    async def enqueue(
        self,
        payload: Dict,
        priority: int = 5,
        task_id: Optional[str] = None
    ) -> asyncio.Future:
        """
        Add task to priority queue.

        Args:
            payload: Request payload
            priority: Priority level (1-10, higher = more important)
            task_id: Optional task identifier

        Returns:
            Future that will be completed when task is processed

        Raises:
            ValueError: If queue is full
        """
        async with self.lock:
            if len(self.queue) >= self.max_size:
                raise ValueError(f"Queue full ({self.max_size} tasks)")

            if task_id is None:
                task_id = f"task_{self.total_queued}"

            future = asyncio.Future()
            task = PrioritizedTask(
                priority=priority,
                timestamp=asyncio.get_event_loop().time(),
                task_id=task_id,
                payload=payload,
                future=future
            )

            heapq.heappush(self.queue, task)
            self.total_queued += 1

            return future

    async def dequeue(self) -> Optional[PrioritizedTask]:
        """
        Get highest-priority task from queue.

        Returns:
            PrioritizedTask or None if queue is empty
        """
        async with self.lock:
            if not self.queue:
                return None

            task = heapq.heappop(self.queue)

            # Record wait time for metrics
            wait_time = asyncio.get_event_loop().time() - task.timestamp
            if task.priority not in self.queue_wait_times:
                self.queue_wait_times[task.priority] = []
            self.queue_wait_times[task.priority].append(wait_time)

            # Keep only last 100 measurements per priority
            if len(self.queue_wait_times[task.priority]) > 100:
                self.queue_wait_times[task.priority] = \
                    self.queue_wait_times[task.priority][-100:]

            self.total_processed += 1

            return task

    async def size(self) -> int:
        """Get current queue size."""
        async with self.lock:
            return len(self.queue)

    async def get_stats(self) -> Dict:
        """Get queue statistics."""
        async with self.lock:
            # Calculate average wait times by priority
            avg_wait_times = {}
            for priority, times in self.queue_wait_times.items():
                if times:
                    avg_wait_times[priority] = sum(times) / len(times)

            # Count tasks by priority in current queue
            priority_counts = {}
            for task in self.queue:
                priority_counts[task.priority] = \
                    priority_counts.get(task.priority, 0) + 1

            return {
                'queue_size': len(self.queue),
                'total_queued': self.total_queued,
                'total_processed': self.total_processed,
                'avg_wait_times_ms': {
                    p: t * 1000 for p, t in avg_wait_times.items()
                },
                'current_priorities': priority_counts,
                'utilization': len(self.queue) / self.max_size if self.max_size > 0 else 0,
            }

# Global priority queue
_priority_queue = PriorityQueue(max_queue_size=1000)

def get_priority_queue() -> PriorityQueue:
    """Get the global priority queue instance."""
    return _priority_queue

# Priority levels for common task types
PRIORITY_CRITICAL = 10  # System-critical requests
PRIORITY_HIGH = 8       # User-facing real-time requests
PRIORITY_NORMAL = 5     # Standard requests
PRIORITY_LOW = 3        # Background tasks
PRIORITY_BATCH = 1      # Batch processing

def get_priority_for_task_type(task_type: str) -> int:
    """
    Get recommended priority for a task type.

    Args:
        task_type: Task type from intelligent router

    Returns:
        Recommended priority (1-10)
    """
    priority_map = {
        'classification': PRIORITY_HIGH,     # Fast, user-facing
        'extraction': PRIORITY_NORMAL,       # Medium importance
        'generation': PRIORITY_NORMAL,       # Standard
        'embedding': PRIORITY_LOW,           # Can be batched
        'summarization': PRIORITY_NORMAL,    # Standard
        'analysis': PRIORITY_NORMAL,         # Standard
    }

    return priority_map.get(task_type, PRIORITY_NORMAL)
