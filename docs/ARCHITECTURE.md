# SynapticLlamas Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      SynapticLlamas CLI                         │
│                    (Rich Console Interface)                     │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Distributed Orchestrator                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐     │
│  │   Adaptive   │  │     Load     │  │  Collaborative   │     │
│  │   Strategy   │  │   Balancer   │  │    Workflow      │     │
│  │   Selector   │  │              │  │                  │     │
│  └──────────────┘  └──────────────┘  └──────────────────┘     │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Agent System                           │
│  ┌──────────┐      ┌──────────┐      ┌──────────┐             │
│  │Researcher│  →   │  Critic  │  →   │  Editor  │             │
│  │ (JSON)   │      │  (JSON)  │      │  (JSON)  │             │
│  └──────────┘      └──────────┘      └──────────┘             │
│         │                 │                 │                   │
│         └─────────────────┴─────────────────┘                   │
│                           │                                     │
│                           ▼                                     │
│                  ┌──────────────────┐                          │
│                  │  TrustCall JSON  │                          │
│                  │   Validation     │                          │
│                  └──────────────────┘                          │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Quality Assurance (AST)                        │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  Agent Voting → Quality Score → Pass/Fail Decision    │    │
│  │  If Fail → Generate Feedback → Re-refine → Re-vote    │    │
│  └────────────────────────────────────────────────────────┘    │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│               JSON to Markdown Conversion                       │
│                    (Display Layer)                              │
└────────────────┬────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Ollama Node Network                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐       │
│  │  Node 1  │  │  Node 2  │  │  Node 3  │  │  Node N  │       │
│  │localhost │  │ GPU Node │  │ CPU Node │  │  Remote  │       │
│  │:11434    │  │:11434    │  │:11434    │  │:11434    │       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. CLI Interface (`main.py`)

**Responsibilities:**
- User interaction and command processing
- Mode switching (standard/distributed/dask)
- Configuration management
- Result display with Rich theming

**Key Features:**
- Interactive command mode
- Single query mode
- Real-time status updates
- Beautiful markdown rendering

---

### 2. Distributed Orchestrator (`distributed_orchestrator.py`)

**Responsibilities:**
- Route requests to appropriate execution mode
- Manage node allocation
- Coordinate parallel/sequential execution
- Aggregate results and metrics

**Execution Modes:**
```
┌─────────────────────────────────────────────────┐
│ SINGLE_NODE                                     │
│ Researcher → Critic → Editor (sequential)      │
│ All on same node                                │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ PARALLEL_SAME_NODE                              │
│ Researcher ┐                                    │
│ Critic     ├─→ All execute in parallel         │
│ Editor     ┘    on same node                    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ PARALLEL_MULTI_NODE                             │
│ Researcher → Node 1                             │
│ Critic     → Node 2  (distributed)              │
│ Editor     → Node 3                             │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ GPU_ROUTING                                     │
│ All agents → GPU nodes only                     │
│ (priority routing to accelerated nodes)         │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ COLLABORATIVE (Sequential with Feedback)        │
│ Phase 1: Researcher (initial)                   │
│ Phase 2: Critic (review)                        │
│ Phase 3: Researcher (refine) - Can be parallel │
│ Phase 4: Editor (synthesize)                    │
│ Phase 5: AST Quality Voting (optional)          │
└─────────────────────────────────────────────────┘
```

---

### 3. Adaptive Strategy Selector (`adaptive_strategy.py`)

**Decision Flow:**
```
Input: agent_count, node_count, node_health, history
                    │
                    ▼
    ┌───────────────────────────────┐
    │ Check System Resources        │
    │ - Available nodes             │
    │ - Node health scores          │
    │ - GPU availability            │
    └───────────┬───────────────────┘
                │
                ▼
    ┌───────────────────────────────┐
    │ Analyze Historical Performance│
    │ - Throughput metrics          │
    │ - Performance trends          │
    │ - Overload detection          │
    └───────────┬───────────────────┘
                │
                ▼
    ┌───────────────────────────────┐
    │ Select Optimal Strategy       │
    │ - Single node if 1 available  │
    │ - Multi-node if >1 healthy    │
    │ - GPU routing if GPUs present │
    │ - Consolidate if overloaded   │
    └───────────┬───────────────────┘
                │
                ▼
         Execution Strategy
```

**Learning Mechanism:**
- Tracks last 20 benchmark results per mode
- Calculates performance trends (improving/stable/degrading)
- Only switches if 10-20% improvement expected
- Detects overload (>70% load) and consolidates

---

### 4. Load Balancer (`load_balancer.py`)

**Routing Strategies:**

```
ROUND_ROBIN:
Request 1 → Node A
Request 2 → Node B
Request 3 → Node C
Request 4 → Node A (cycle)

LEAST_LOADED:
Calculate load scores (0.0-1.0)
Select node with minimum load
Updates in real-time

PRIORITY:
Sort by priority scores
Select highest priority healthy node

GPU_FIRST:
Filter for GPU nodes
Fallback to CPU if none available

RANDOM:
Uniform random selection
Useful for load distribution
```

---

### 5. Multi-Agent System

#### Agent Pipeline

```
┌────────────────────────────────────────────────────┐
│                   RESEARCHER                       │
│  Input: User Query                                 │
│  Output: {key_facts, context, topics}             │
│  Role: Information gathering & research            │
└─────────────────┬──────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────┐
│                    CRITIC                          │
│  Input: User Query + Researcher Output             │
│  Output: {issues, biases, strengths, recommendations}│
│  Role: Quality control & fact-checking             │
└─────────────────┬──────────────────────────────────┘
                  │
                  ▼
┌────────────────────────────────────────────────────┐
│                    EDITOR                          │
│  Input: Query + Researcher + Critic                │
│  Output: {summary, key_points, detailed_explanation,│
│           examples, practical_applications}        │
│  Role: Synthesis & final formatting                │
└────────────────────────────────────────────────────┘
```

#### TrustCall Validation Flow

```
Agent Output (JSON string)
        │
        ▼
┌──────────────────────┐
│  Parse JSON          │
│  Success?            │
└────┬────────────┬────┘
     │ Yes        │ No
     │            │
     │            ▼
     │    ┌──────────────────────┐
     │    │ Extract JSON from    │
     │    │ markdown/text        │
     │    └──────┬───────────────┘
     │           │
     ▼           ▼
┌──────────────────────────────┐
│  Validate Against Schema     │
│  - Check required fields     │
│  - Validate types            │
│  - Identify violations       │
└────┬─────────────────────┬───┘
     │ Valid              │ Invalid
     │                    │
     │                    ▼
     │         ┌─────────────────────┐
     │         │ Generate JSON Patch │
     │         │ Repair Prompt       │
     │         └──────┬──────────────┘
     │                │
     │                ▼
     │         ┌─────────────────────┐
     │         │ LLM: Fix with Patch │
     │         │ (up to 3 attempts)  │
     │         └──────┬──────────────┘
     │                │
     │                ▼
     │         ┌─────────────────────┐
     │         │ Apply JSON Patch    │
     │         └──────┬──────────────┘
     │                │
     │                ▼
     └────────────► Re-validate
                      │
                      ▼
                 Valid JSON ✓
```

---

### 6. Collaborative Workflow (`collaborative_workflow.py`)

**Sequential Workflow with Feedback Loops:**

```
User Query
    │
    ▼
┌─────────────────────────────────────────┐
│ Phase 1: Initial Research               │
│ Researcher processes query              │
│ Time: ~15-20s                            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Phase 2: Critique                       │
│ Critic reviews research                 │
│ Identifies gaps, issues, strengths      │
│ Time: ~30-50s                            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Phase 3: Refinement (Optional)          │
│                                         │
│ Single Node Mode:                       │
│   Researcher refines sequentially       │
│   N iterations                          │
│                                         │
│ Distributed Mode:                       │
│   Generate N varied refinement prompts  │
│   Execute in parallel on N nodes        │
│   Select best refinement                │
│                                         │
│ Time: ~50-100s per iteration            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Phase 4: Final Synthesis                │
│ Editor synthesizes all inputs           │
│ Creates structured JSON output          │
│ Time: ~40-120s                           │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Phase 5: AST Quality Voting (Optional)  │
│ See AST section below                   │
└─────────────────────────────────────────┘
```

---

### 7. AST Quality Voting (`quality_assurance.py`)

**Quality Assurance Flow:**

```
Editor Output (JSON)
        │
        ▼
┌─────────────────────────────────────────┐
│ Convert to Markdown                     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Initialize Voting Agents                │
│ - Researcher (evaluator)                │
│ - Critic (evaluator)                    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Each Agent Scores 0.0-1.0               │
│ Criteria:                               │
│ - Accuracy & correctness                │
│ - Completeness                          │
│ - Clarity & readability                 │
│ - Structure & organization              │
│ - Depth & detail                        │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│ Aggregate Scores (average)              │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
    Score >= Threshold   Score < Threshold
        │                   │
        │                   ▼
        │         ┌─────────────────────────┐
        │         │ Generate Improvement    │
        │         │ Feedback                │
        │         │ - List all issues       │
        │         │ - Agent reasoning       │
        │         │ - Specific gaps         │
        │         └──────┬──────────────────┘
        │                │
        │                ▼
        │         ┌─────────────────────────┐
        │         │ Editor Re-refines       │
        │         │ (with feedback)         │
        │         └──────┬──────────────────┘
        │                │
        │                ▼
        │         ┌─────────────────────────┐
        │         │ Re-vote on New Output   │
        │         │ (up to max_retries)     │
        │         └──────┬──────────────────┘
        │                │
        └────────────────┤
                         ▼
                  Final Output
            (Passed or Max Retries)
```

**Quality Scoring Example:**

```
Researcher: 0.82/1.0
"Comprehensive but needs more examples"
Issues: ["Lacks concrete examples", "Could expand theory"]

Critic: 0.92/1.0
"Well structured, minor gaps"
Issues: ["Missing practical applications"]

Aggregate: 0.87/1.0
Threshold: 0.90
Result: FAIL → Trigger re-refinement
```

---

### 8. Node Management

#### Node Registry (`node_registry.py`)

```
┌────────────────────────────────────────┐
│          Node Registry                 │
│  ┌──────────────────────────────────┐ │
│  │ Node 1: localhost:11434          │ │
│  │ - Health: ✓ (last check: 2s ago) │ │
│  │ - Load: 0.35                     │ │
│  │ - GPU: Yes (NVIDIA RTX 3090)     │ │
│  │ - Priority: 10                   │ │
│  │ - Failures: 0/5                  │ │
│  └──────────────────────────────────┘ │
│                                        │
│  ┌──────────────────────────────────┐ │
│  │ Node 2: 192.168.1.100:11434      │ │
│  │ - Health: ✓                      │ │
│  │ - Load: 0.62                     │ │
│  │ - GPU: No                        │ │
│  │ - Priority: 5                    │ │
│  │ - Failures: 0/5                  │ │
│  └──────────────────────────────────┘ │
└────────────────────────────────────────┘

Operations:
- add_node(url, name, priority)
- remove_node(url)
- get_healthy_nodes()
- get_gpu_nodes()
- health_check_all()
- discover_nodes(cidr)
- save_config(file)
- load_config(file)
```

#### Network Discovery (`network_utils.py`)

```
Auto-detect Local Network
        │
        ▼
┌──────────────────────┐
│ Get Local IP        │
│ Connect to 8.8.8.8  │
│ Extract IP          │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────┐
│ Calculate CIDR      │
│ /24 network mask    │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────┐
│ Parallel Scan       │
│ - 50 workers        │
│ - Port 11434        │
│ - Timeout 1s/node   │
└────┬─────────────────┘
     │
     ▼
┌──────────────────────┐
│ Verify Ollama       │
│ GET /api/tags       │
└────┬─────────────────┘
     │
     ▼
  Found Nodes
```

---

### 9. Data Flow

**Standard Parallel Mode:**
```
User Query
    │
    ├────────────┬────────────┐
    │            │            │
    ▼            ▼            ▼
Researcher    Critic      Editor
(Node 1)     (Node 2)    (Node 3)
    │            │            │
    │ (parallel) │            │
    └────────────┴────────────┘
                 │
                 ▼
         Merge JSON Outputs
                 │
                 ▼
        JSON → Markdown
                 │
                 ▼
            Display
```

**Collaborative Mode with AST:**
```
User Query
    │
    ▼
Researcher (Phase 1)
    │
    ▼
Critic (Phase 2)
    │
    ▼
Researcher Refinement (Phase 3)
    │ (can be distributed)
    ▼
Editor Synthesis (Phase 4)
    │
    ▼
AST Voting (Phase 5)
    │
    ├─ PASS ──────────────┐
    │                     │
    └─ FAIL              │
        │                │
        ▼                │
    Re-refinement        │
        │                │
        └────────────────┤
                         ▼
                  JSON → Markdown
                         │
                         ▼
                     Display
```

---

## Performance Characteristics

### Latency by Mode

| Mode | Avg Time | Quality | Use Case |
|------|----------|---------|----------|
| Parallel (No Collab) | 50-100s | Medium | Fast answers |
| Collaborative | 150-250s | High | Balanced |
| Collab + AST (0.7) | 200-300s | Very High | Quality |
| Collab + AST (0.9) | 250-400s | Excellent | Critical |

### Resource Usage

```
Single Node:
- CPU: 80-100% during generation
- Memory: ~2-4GB per model
- Network: Minimal

Multi-Node (3 nodes):
- CPU: 30-40% per node
- Parallel speedup: ~2-2.5x
- Network: Moderate (JSON transfer)

Distributed Refinement:
- Parallel speedup: Up to Nx (N nodes)
- Network: Higher (multiple refinements)
```

---

## Extension Points

### Adding New Agents

```python
from agents.base_agent import BaseAgent

class MyCustomAgent(BaseAgent):
    def __init__(self, model="llama3.2", timeout=300):
        super().__init__("MyAgent", model, timeout=timeout)
        self.expected_schema = {
            "field1": str,
            "field2": list
        }

    def process(self, input_data):
        system_prompt = "Your role..."
        prompt = f"Process: {input_data}"
        return self.call_ollama(prompt, system_prompt)
```

### Adding Custom Strategies

```python
from adaptive_strategy import ExecutionMode

# Add to ExecutionMode enum
class ExecutionMode(Enum):
    MY_CUSTOM_MODE = "my_custom"

# Implement in DistributedOrchestrator
def _execute_my_custom_mode(self, agents, input_data, strategy):
    # Your implementation
    pass
```

### Adding New Routing Strategies

```python
from load_balancer import RoutingStrategy

class RoutingStrategy(Enum):
    MY_ROUTING = "my_routing"

# Implement in OllamaLoadBalancer
```

---

## Configuration Files

### Node Config Format

```json
{
  "nodes": [
    {
      "url": "http://localhost:11434",
      "name": "local-gpu",
      "priority": 10
    },
    {
      "url": "http://192.168.1.100:11434",
      "name": "server-1",
      "priority": 5
    }
  ]
}
```

### Benchmark Results Format

```json
{
  "summary": {
    "total_tests": 12,
    "successful_tests": 12,
    "configurations_tested": 4
  },
  "configuration_performance": {
    "Parallel (No Collab)": {
      "avg_time": 65.3,
      "avg_quality_score": 0.0
    },
    "Collaborative + AST": {
      "avg_time": 245.7,
      "avg_quality_score": 0.85
    }
  }
}
```

---

## Security Considerations

- **No authentication** - Assumes trusted network
- **Node discovery** - Scans network (can be disabled)
- **API tokens** - Not currently implemented
- **Input validation** - JSON schema enforcement via TrustCall
- **Rate limiting** - Not implemented (rely on Ollama)

---

## Scalability Limits

- **Node count**: Tested up to 10 nodes
- **Agent count**: 3 fixed (Researcher, Critic, Editor)
- **Concurrent queries**: 1 at a time (no queuing)
- **Model size**: Limited by Ollama node capacity
- **Network latency**: Assumes <100ms between nodes

---

## Future Architecture Enhancements

1. **Message Queue** - Add Redis/RabbitMQ for request queuing
2. **Web API** - FastAPI REST interface
3. **WebSocket** - Real-time updates
4. **Caching** - Redis cache for repeated queries
5. **Model Adapter** - Support OpenAI, Anthropic APIs
6. **Horizontal Scaling** - Multiple orchestrator instances
7. **Monitoring** - Prometheus metrics, Grafana dashboards
8. **Auth** - JWT tokens, API keys
9. **Multi-tenancy** - User isolation, quotas
10. **Agent Plugins** - Dynamic agent loading

---

For implementation details, see the source code in each module.
