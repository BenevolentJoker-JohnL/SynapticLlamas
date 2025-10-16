# SynapticLlamas RAG Commands - Quick Reference

## How to Use FlockParser RAG Integration

### Setup (One-Time)

```bash
cd /home/joker/SynapticLlamas
python main.py --interactive
```

### Enable RAG

```bash
SynapticLlamas> rag on
✅ FlockParser RAG ENABLED
   Research queries will be enhanced with PDF context
```

### Check Status

```bash
SynapticLlamas> status

┌───────────────────────────────────────────────────────────────┐
│                     SYNAPTICLLAMAS STATUS                      │
├───────────────────────┬───────────────────────────────────────┤
│ Mode                  │ distributed                            │
│ Model                 │ llama3.2                               │
│ Collaborative         │ ON                                     │
│ FlockParser RAG       │ ON (12 docs, 247 chunks)              │
│ SOLLOL Routing        │ Intelligent                            │
└───────────────────────┴───────────────────────────────────────┘
```

### Issue Research Query (Automatic RAG Enhancement)

**Just type your query directly - no special command needed!**

```bash
SynapticLlamas> Explain quantum entanglement in topological systems
```

**What Happens Automatically:**

1. ✅ Content detector recognizes this as RESEARCH
2. ✅ FlockParser RAG is enabled
3. ✅ Query gets automatically enhanced with PDF excerpts
4. ✅ Collaborative workflow runs with enhanced context
5. ✅ Final report includes citations

**Console Output:**
```bash
SynapticLlamas> Explain quantum entanglement in topological systems

📚 Enhancing query with FlockParser document context...
🔍 Querying FlockParser knowledge base: 'Explain quantum entanglement...'
   📚 Found 15 relevant chunks from 3 document(s)
   🎯 Top similarity: 0.87
   📄 Prepared context: 15 chunks, 3 sources, ~1847 tokens
✅ Enhanced query with 3 source document(s)

🤝 Using collaborative workflow mode

🎯 Phase 1: Initial Research
[Researcher analyzing with PDF context...]

🔍 Phase 2: Critical Review
[Critic reviewing...]

✍️ Phase 3: Synthesis & Editing
[Editor synthesizing...]

📊 METRICS
Total time: 23.4s
Sources cited: 3 documents

## 📚 Source Documents
1. majorana_fermions.pdf
2. quantum_entanglement.pdf
3. topology_quantum_computing.pdf
```

## All Available Commands

### RAG Commands

| Command | Description | Example |
|---------|-------------|---------|
| `rag on` | Enable FlockParser RAG | `SynapticLlamas> rag on` |
| `rag off` | Disable FlockParser RAG | `SynapticLlamas> rag off` |
| `status` | Show RAG status | Shows "(12 docs, 247 chunks)" |

### Mode Commands

| Command | Description | Impact on RAG |
|---------|-------------|---------------|
| `mode distributed` | Enable distributed mode | ✅ RAG works |
| `mode dask` | Enable Dask mode | ✅ RAG works |
| `mode standard` | Standard mode | ❌ RAG disabled |

**Note:** RAG requires `distributed` or `dask` mode!

### Collaboration Commands

| Command | Description | Impact on RAG |
|---------|-------------|---------------|
| `collab on` | Enable collaborative workflow | ✅ Recommended for RAG |
| `collab off` | Disable collaborative | RAG still works |

**Best Practice:** Use `collab on` with RAG for best research reports!

### Model Commands

| Command | Description | Example |
|---------|-------------|---------|
| `model <name>` | Set default model | `model llama3.1:70b` |
| `synthesis <name>` | Set synthesis model (Phase 4) | `synthesis llama3.1:405b` |

## Complete Workflow Example

### Scenario: Research Quantum Computing with PDFs

```bash
# 1. Start SynapticLlamas
cd /home/joker/SynapticLlamas
python main.py --interactive

# 2. Configure for RAG-enhanced research
SynapticLlamas> mode distributed
✅ Switched to distributed mode

SynapticLlamas> collab on
✅ Collaborative workflow ENABLED

SynapticLlamas> rag on
✅ FlockParser RAG ENABLED
   Research queries will be enhanced with PDF context

SynapticLlamas> model llama3.1:70b
✅ Default model set to llama3.1:70b

SynapticLlamas> synthesis llama3.1:405b
✅ Synthesis model set to llama3.1:405b
   Phase 1-3: llama3.1:70b
   Phase 4: llama3.1:405b

# 3. Check configuration
SynapticLlamas> status
┌───────────────────────┬───────────────────────────────────┐
│ Mode                  │ distributed                        │
│ Model                 │ llama3.1:70b                       │
│ Synthesis Model       │ llama3.1:405b                      │
│ Collaborative         │ ON                                 │
│ FlockParser RAG       │ ON (12 docs, 247 chunks)          │
│ SOLLOL Routing        │ Intelligent                        │
└───────────────────────┴───────────────────────────────────┘

# 4. Issue research query (no special command needed!)
SynapticLlamas> Explain how topological quantum computers use anyons for error-free computation

📚 Enhancing query with FlockParser document context...
🔍 Querying FlockParser knowledge base...
   📚 Found 15 relevant chunks from 4 document(s)
   🎯 Top similarity: 0.89
✅ Enhanced query with 4 source document(s)

🤝 Using collaborative workflow mode

[Research process with PDF evidence...]

## Final Report

[Comprehensive analysis with citations]

## 📚 Source Documents
1. topology_quantum_computing.pdf
2. anyons_braiding.pdf
3. quantum_error_correction.pdf
4. majorana_fermions.pdf
```

## Content Type Detection

SynapticLlamas **automatically** detects when to use RAG:

### Triggers RAG (RESEARCH Content)

✅ "Explain quantum entanglement"
✅ "What are topological insulators?"
✅ "How does quantum error correction work?"
✅ "Analyze the implications of Bell's theorem"
✅ "Compare classical vs quantum computing"

**Pattern:** Technical questions, explanations, comparisons, analysis

### Does NOT Trigger RAG (Non-Research Content)

❌ "Write a story about a quantum computer" (STORYTELLING)
❌ "Create a Python function for sorting" (CODE)
❌ "Write a poem about entanglement" (CREATIVE)

**Pattern:** Creative writing, code generation, fiction

## Behind the Scenes (Automatic)

When you type a research query:

```python
# 1. Content detection (automatic)
content_type = detect_content_type("Explain quantum entanglement")
# Returns: ContentType.RESEARCH

# 2. RAG enhancement (automatic if enabled)
if flockparser_enabled and content_type == RESEARCH:
    enhanced_query, sources = flockparser_adapter.enhance_research_query(
        query="Explain quantum entanglement",
        top_k=15,
        max_context_tokens=2000
    )
    # Query now includes PDF excerpts!

# 3. Collaborative workflow (automatic if enabled)
if collaborative_mode:
    result = orchestrator.run(
        enhanced_query,  # With PDF context
        collaborative=True
    )
    # All 3 agents receive PDF evidence

# 4. Citations added (automatic)
report = flockparser_adapter.generate_document_report(
    query, agent_insights, sources
)
# Final report includes reference section
```

**You don't trigger any of this manually - it happens automatically when:**
1. RAG is enabled (`rag on`)
2. Mode is distributed/dask
3. Query is detected as RESEARCH content

## Configuration File

Settings persist in `config.json`:

```json
{
  "mode": "distributed",
  "model": "llama3.1:70b",
  "synthesis_model": "llama3.1:405b",
  "collaborative_mode": true,
  "flockparser_enabled": true,
  "refinement_rounds": 1,
  "agent_timeout": 300
}
```

## Quick Start Commands

**Optimal setup for RAG-enhanced research:**

```bash
# Start with optimal configuration
python main.py --interactive

# One-time setup
SynapticLlamas> mode distributed
SynapticLlamas> collab on
SynapticLlamas> rag on
SynapticLlamas> model llama3.1:70b

# Now just type research queries!
SynapticLlamas> Explain topological quantum computation
```

## Disabling RAG

```bash
SynapticLlamas> rag off
✅ FlockParser RAG DISABLED

# Now queries run without PDF enhancement
SynapticLlamas> Explain quantum entanglement
⚡ Processing...
[Research without PDF context]
```

## Summary

**You don't issue a special command to use RAG** - you just:

1. **Enable it once:** `rag on`
2. **Type research queries:** They're automatically enhanced with PDFs
3. **That's it!** No special syntax needed

The system **automatically**:
- Detects research queries
- Searches FlockParser knowledge base
- Enhances queries with PDF excerpts
- Includes citations in reports

**Best Configuration:**
```bash
mode distributed  # Required for RAG
collab on        # Best for comprehensive reports
rag on           # Enable PDF enhancement
```

Then just ask your research questions naturally! 🚀📚
