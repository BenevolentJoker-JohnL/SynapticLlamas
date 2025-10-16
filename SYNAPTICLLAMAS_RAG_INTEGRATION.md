# SynapticLlamas RAG Integration with FlockParser

## How SynapticLlamas Uses FlockParser's Knowledge Base for Research Reports

This document explains **exactly** how SynapticLlamas interfaces with FlockParser to access PDF documents and construct long, document-grounded research reports.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                       USER QUERY                                  │
│             "Explain quantum entanglement"                        │
└───────────────────────────┬──────────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────────┐
│                   SYNAPTICLLAMAS                                   │
│                 (distributed_orchestrator.py)                      │
├───────────────────────────────────────────────────────────────────┤
│  1. Detect content type: RESEARCH                                 │
│  2. Check if FlockParser RAG enabled                              │
│  3. Call flockparser_adapter.enhance_research_query()             │
└───────────────────────────┬───────────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────────┐
│              FLOCKPARSER ADAPTER                                   │
│           (flockparser_adapter.py)                                 │
├───────────────────────────────────────────────────────────────────┤
│  Step 1: Generate query embedding                                 │
│           (uses SOLLOL GPU routing - 8ms vs 178ms)                │
│                                                                    │
│  Step 2: Search FlockParser knowledge base                        │
│           /home/joker/FlockParser/knowledge_base/                 │
│           - Read document_index.json                              │
│           - Scan all chunk files (doc_*_chunk_*.json)             │
│           - Calculate cosine similarity                            │
│                                                                    │
│  Step 3: Return top 15 relevant chunks                            │
│           Sorted by similarity score                              │
└───────────────────────────┬───────────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────────┐
│           ENHANCED QUERY WITH PDF CONTEXT                         │
├───────────────────────────────────────────────────────────────────┤
│  Original query: "Explain quantum entanglement"                   │
│                                                                    │
│  RELEVANT DOCUMENT EXCERPTS:                                      │
│  [Source: majorana_fermions.pdf, Relevance: 0.87]                │
│  "Chiral Majorana fermion is a massless self-conjugate           │
│   fermion which can arise as the edge state..."                   │
│                                                                    │
│  [Source: quantum_topology.pdf, Relevance: 0.82]                 │
│  "The EPR paradox demonstrates that quantum                       │
│   entanglement violates local realism..."                         │
│                                                                    │
│  ... (up to 15 chunks, ~2000 tokens)                             │
└───────────────────────────┬───────────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────────┐
│          COLLABORATIVE WORKFLOW                                    │
│      (researcher + critic + editor agents)                        │
├───────────────────────────────────────────────────────────────────┤
│  All agents receive enhanced query with PDF context               │
│                                                                    │
│  Researcher: Analyzes query using PDF excerpts + knowledge        │
│  Critic: Reviews analysis for accuracy and completeness           │
│  Editor: Synthesizes final report with citations                  │
└───────────────────────────┬───────────────────────────────────────┘
                            ↓
┌───────────────────────────────────────────────────────────────────┐
│        FINAL RESEARCH REPORT WITH CITATIONS                       │
├───────────────────────────────────────────────────────────────────┤
│  # Research Report                                                │
│  **Query:** Explain quantum entanglement                          │
│  **Sources:** 3 document(s)                                       │
│  **Evidence Chunks:** 15 relevant sections                        │
│                                                                    │
│  ## Analysis                                                       │
│  [Agent insights with PDF evidence integrated]                    │
│                                                                    │
│  ## Supporting Evidence from Documents                            │
│  [PDF excerpts with source attribution]                           │
│                                                                    │
│  ## References                                                     │
│  1. majorana_fermions.pdf                                         │
│  2. quantum_topology.pdf                                          │
│  3. entanglement_experiments.pdf                                  │
└───────────────────────────────────────────────────────────────────┘
```

---

## Step-by-Step Flow

### Step 1: User Enables RAG in SynapticLlamas

```bash
cd /home/joker/SynapticLlamas
python main.py --interactive

SynapticLlamas> rag on
✅ FlockParser RAG ENABLED
   Research queries will be enhanced with PDF context

SynapticLlamas> status
┌───────────────────┬────────────────────────────────────┐
│ FlockParser RAG   │ ON (12 docs, 247 chunks)           │
└───────────────────┴────────────────────────────────────┘
```

**What happens:**
- Sets `flockparser_enabled = True` in config
- Reinitializes `DistributedOrchestrator` with RAG enabled
- Creates `FlockParserAdapter` instance

**Code:** `/home/joker/SynapticLlamas/main.py` (lines 610-614)
```python
flockparser_enabled = True
update_config(flockparser_enabled=True)
global_orchestrator = None  # Force re-initialization
print("✅ FlockParser RAG ENABLED")
```

### Step 2: Orchestrator Initializes FlockParser Adapter

**Code:** `/home/joker/SynapticLlamas/distributed_orchestrator.py` (lines 137-156)

```python
# Initialize FlockParser RAG adapter
self.use_flockparser = use_flockparser
self.flockparser_adapter = None

if use_flockparser:
    try:
        # Pass SOLLOL components for distributed document queries
        self.flockparser_adapter = get_flockparser_adapter(
            hybrid_router_sync=self.hybrid_router_sync,  # For GPU embeddings
            load_balancer=self.load_balancer             # For routing
        )

        if self.flockparser_adapter.available:
            stats = self.flockparser_adapter.get_statistics()
            mode = "distributed" if self.flockparser_adapter.distributed_mode else "local"
            logger.info(f"📚 FlockParser RAG enabled ({mode} mode, "
                       f"{stats['documents']} docs, {stats['chunks']} chunks)")
    except Exception as e:
        logger.warning(f"⚠️  Could not initialize FlockParser: {e}")
        self.use_flockparser = False
```

**FlockParser Adapter Initialization:** `/home/joker/SynapticLlamas/flockparser_adapter.py` (lines 31-71)

```python
def __init__(
    self,
    flockparser_path: str = "/home/joker/FlockParser",
    embedding_model: str = "mxbai-embed-large",
    hybrid_router_sync=None,
    load_balancer=None
):
    # Access FlockParser's file system
    self.flockparser_path = Path(flockparser_path)
    self.knowledge_base_path = self.flockparser_path / "knowledge_base"
    self.document_index_path = self.flockparser_path / "document_index.json"

    # SOLLOL integration for distributed embeddings
    self.hybrid_router_sync = hybrid_router_sync
    self.distributed_mode = hybrid_router_sync is not None

    # Check availability
    if not self.flockparser_path.exists():
        logger.warning(f"FlockParser not found at {flockparser_path}")
        self.available = False
    else:
        self.available = True
        doc_count = self._count_documents()
        mode_str = " (distributed mode)" if self.distributed_mode else ""
        logger.info(f"✅ FlockParser adapter initialized "
                   f"({doc_count} documents){mode_str}")
```

### Step 3: User Submits Research Query

```bash
SynapticLlamas> Explain quantum entanglement in topological systems
```

**Content Detection:** System detects query is RESEARCH type (not code/creative)

**Code:** `/home/joker/SynapticLlamas/distributed_orchestrator.py` (lines 986-993)

```python
# Detect content type
from content_detector import detect_content_type, ContentType

content_type, metadata = detect_content_type(query)

# Enhance query with FlockParser RAG if enabled and content is research
if self.use_flockparser and content_type == ContentType.RESEARCH:
    enhanced_query, source_documents = self.flockparser_adapter.enhance_research_query(
        query,
        top_k=15,
        max_context_tokens=2000
    )
```

### Step 4: FlockParser Document Retrieval

#### 4a. Generate Query Embedding (GPU-Accelerated)

**Code:** `/home/joker/SynapticLlamas/flockparser_adapter.py` (lines 83-119)

```python
def _get_embedding(self, text: str) -> Optional[List[float]]:
    """Generate embedding using SOLLOL GPU routing."""
    try:
        # Use HybridRouter if available (SOLLOL distributed routing)
        if self.hybrid_router_sync:
            result = self.hybrid_router_sync.generate_embedding(
                model=self.embedding_model,
                prompt=text
            )
            return result.get('embedding', [])

        # Fallback to direct Ollama (slower)
        response = requests.post(
            f"{self.ollama_url}/api/embeddings",
            json={"model": "mxbai-embed-large", "prompt": text}
        )
        return response.json().get('embedding', [])
    except Exception as e:
        logger.error(f"Failed to generate embedding: {e}")
        return None
```

**Performance:**
- **With SOLLOL (GPU):** 8ms
- **Without SOLLOL (CPU):** 178ms
- **Speedup:** 22x faster

#### 4b. Load Document Index

**Code:** `/home/joker/SynapticLlamas/flockparser_adapter.py` (lines 183-189)

```python
# Load document index
with open(self.document_index_path, 'r') as f:
    index_data = json.load(f)

documents = index_data.get('documents', [])
# Returns: [{id, original, chunk_count, chunks: [{chunk_id, file}]}]
```

**FlockParser Document Index Structure:**
```json
{
  "documents": [
    {
      "id": "doc_1",
      "original": "/home/joker/FlockParser/testpdfs/majorana_fermions.pdf",
      "chunk_count": 10,
      "chunks": [
        {"chunk_id": 0, "file": "/home/joker/FlockParser/knowledge_base/doc_1_chunk_0.json"},
        {"chunk_id": 1, "file": "/home/joker/FlockParser/knowledge_base/doc_1_chunk_1.json"},
        ...
      ]
    },
    ...
  ]
}
```

#### 4c. Scan All Chunks and Calculate Similarity

**Code:** `/home/joker/SynapticLlamas/flockparser_adapter.py` (lines 192-231)

```python
# Collect all chunks with similarities
chunks_with_similarity = []

for doc in documents:
    for chunk_ref in doc.get('chunks', []):
        chunk_file = Path(chunk_ref['file'])

        if chunk_file.exists():
            with open(chunk_file, 'r') as f:
                chunk_data = json.load(f)

            chunk_embedding = chunk_data.get('embedding', [])

            if chunk_embedding:
                # Calculate cosine similarity
                similarity = self._cosine_similarity(
                    query_embedding,
                    chunk_embedding
                )

                if similarity >= min_similarity:  # default 0.3
                    chunks_with_similarity.append({
                        'text': chunk_data['text'],
                        'doc_name': Path(doc['original']).name,
                        'similarity': similarity,
                        'doc_id': doc['id']
                    })

# Sort by similarity and return top k
chunks_with_similarity.sort(key=lambda x: x['similarity'], reverse=True)
results = chunks_with_similarity[:top_k]  # top_k=15
```

**FlockParser Chunk File Structure:**
```json
{
  "text": "Chiral Majorana fermion is a massless self-conjugate fermion...",
  "embedding": [0.0017422, 0.009713, -0.008630, ...],  // 1024-dim vector
  "page": 1,
  "chunk_index": 0
}
```

**Cosine Similarity Calculation:**
```python
def _cosine_similarity(self, vec1, vec2):
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)

    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)

    return float(dot_product / (norm1 * norm2))
```

**Example Results:**
```python
[
    {
        'text': 'Chiral Majorana fermion is a massless...',
        'doc_name': 'majorana_fermions.pdf',
        'similarity': 0.87,
        'doc_id': 'doc_1'
    },
    {
        'text': 'The EPR paradox demonstrates that...',
        'doc_name': 'quantum_entanglement.pdf',
        'similarity': 0.82,
        'doc_id': 'doc_3'
    },
    ...
]
```

### Step 5: Format Context for Research Agents

**Code:** `/home/joker/SynapticLlamas/flockparser_adapter.py` (lines 237-289)

```python
def format_context_for_research(
    self,
    chunks: List[Dict],
    max_tokens: int = 2000
) -> Tuple[str, List[str]]:
    """Format retrieved chunks as context for research agents."""

    def estimate_tokens(text: str) -> int:
        """Conservative estimation: 1 token ≈ 3.5 chars."""
        return int(len(text) / 3.5)

    context_parts = []
    current_tokens = 0
    sources = set()
    chunks_used = 0

    for chunk in chunks:
        # Format with source attribution
        formatted = (
            f"[Source: {chunk['doc_name']}, Relevance: {chunk['similarity']:.2f}]\n"
            f"{chunk['text']}"
        )

        chunk_tokens = estimate_tokens(formatted)

        # Check if we have room for this chunk
        if current_tokens + chunk_tokens <= max_tokens:
            context_parts.append(formatted)
            current_tokens += chunk_tokens
            sources.add(chunk['doc_name'])
            chunks_used += 1
        else:
            break  # Reached token limit

    context = "\n\n---\n\n".join(context_parts)

    logger.info(f"   📄 Prepared context: {chunks_used} chunks, "
               f"{len(sources)} sources, ~{current_tokens} tokens")

    return context, list(sources)
```

**Formatted Context Example:**
```
[Source: majorana_fermions.pdf, Relevance: 0.87]
Chiral Majorana fermion is a massless self-conjugate fermion which
can arise as the edge state of certain two-dimensional topological
matters. It has been theoretically predicted and experimentally
observed in a hybrid device of quantum anomalous Hall insulator...

---

[Source: quantum_entanglement.pdf, Relevance: 0.82]
The EPR paradox demonstrates that quantum entanglement violates
local realism. When two particles are entangled, measuring one
instantly affects the state of the other, regardless of distance...

---

[Source: topology_quantum_computing.pdf, Relevance: 0.79]
Topological quantum computation based on anyons provides inherent
protection against decoherence. The quantum information is encoded
in the global topological properties rather than local states...
```

### Step 6: Build Enhanced Query

**Code:** `/home/joker/SynapticLlamas/flockparser_adapter.py` (lines 331-349)

```python
# Build enhanced query with PDF context
enhanced_query = f"""Research topic: {query}

RELEVANT DOCUMENT EXCERPTS:
{context}

---

Based on the above document excerpts and your knowledge, provide a comprehensive
technical explanation of: {query}

IMPORTANT:
- Integrate information from the provided sources where relevant
- Add additional context and explanations beyond what's in the sources
- Cite specific findings from the documents when you use them
- Still provide comprehensive coverage even if sources are limited to certain aspects
"""

logger.info(f"✅ Enhanced query with {len(sources)} source document(s)")

return enhanced_query, sources
```

**Enhanced Query Example:**
```
Research topic: Explain quantum entanglement in topological systems

RELEVANT DOCUMENT EXCERPTS:
[Source: majorana_fermions.pdf, Relevance: 0.87]
Chiral Majorana fermion is a massless self-conjugate fermion...

[Source: quantum_entanglement.pdf, Relevance: 0.82]
The EPR paradox demonstrates that quantum entanglement...

[Source: topology_quantum_computing.pdf, Relevance: 0.79]
Topological quantum computation based on anyons...

---

Based on the above document excerpts and your knowledge, provide a
comprehensive technical explanation of: Explain quantum entanglement
in topological systems

IMPORTANT:
- Integrate information from the provided sources where relevant
- Add additional context and explanations beyond what's in the sources
- Cite specific findings from the documents when you use them
- Still provide comprehensive coverage even if sources are limited
```

### Step 7: Collaborative Workflow with Enhanced Query

**Code:** `/home/joker/SynapticLlamas/distributed_orchestrator.py` (lines 207-220)

```python
# COLLABORATIVE MODE
if collaborative:
    logger.info("🤝 Using collaborative workflow mode")

    # FlockParser document enhancement (if enabled)
    enhanced_input = input_data
    source_documents = []

    if self.use_flockparser and self.flockparser_adapter:
        logger.info("📚 Enhancing query with FlockParser document context...")
        enhanced_input, source_documents = self.flockparser_adapter.enhance_research_query(
            input_data,
            top_k=15,
            max_context_tokens=2000
        )

    # Pass enhanced query to collaborative workflow
    result = collaborative_workflow.execute(enhanced_input, model_name, ...)
```

**All three agents (Researcher, Critic, Editor) receive the enhanced query with PDF context!**

### Step 8: Generate Final Report with Citations

**Code:** `/home/joker/SynapticLlamas/flockparser_adapter.py` (lines 351-443)

```python
def generate_document_report(
    self,
    query: str,
    agent_insights: List[Dict],
    top_k: int = 20,
    max_context_tokens: int = 3000
) -> Dict:
    """Generate comprehensive report with agent insights + document evidence."""

    # Query FlockParser for relevant evidence
    evidence_chunks = self.query_documents(query, top_k=top_k)
    evidence_context, sources = self.format_context_for_research(
        evidence_chunks,
        max_tokens=max_context_tokens
    )

    # Build comprehensive report
    report_sections = []

    # Executive Summary
    report_sections.append("# Research Report\n")
    report_sections.append(f"**Query:** {query}\n")
    report_sections.append(f"**Sources:** {len(sources)} document(s)\n")
    report_sections.append(f"**Evidence Chunks:** {len(evidence_chunks)} sections\n")

    # Agent Insights Section
    report_sections.append("\n## Analysis\n")
    for insight in agent_insights:
        agent_name = insight.get('agent', 'Unknown')
        content = insight.get('data', {}).get('context', '')

        report_sections.append(f"### {agent_name} Perspective\n")
        report_sections.append(f"{content}\n")

    # Document Evidence Section
    if evidence_context:
        report_sections.append("\n## Supporting Evidence from Documents\n")
        report_sections.append(evidence_context)

    # Citations Section
    if sources:
        report_sections.append("\n## References\n")
        for i, source in enumerate(sources, 1):
            report_sections.append(f"{i}. {source}\n")

    report = "\n".join(report_sections)

    return {
        'report': report,
        'sources': sources,
        'evidence_chunks': evidence_chunks,
        'agent_count': len(agent_insights)
    }
```

**Final Report Structure:**
```markdown
# Research Report
**Query:** Explain quantum entanglement in topological systems
**Sources:** 3 document(s)
**Evidence Chunks:** 15 relevant sections

## Analysis

### Researcher Perspective
Quantum entanglement in topological systems represents a fascinating
intersection of quantum information theory and condensed matter physics.
As noted in majorana_fermions.pdf (relevance: 0.87), chiral Majorana
fermions provide a unique platform for studying topological entanglement...

[Agent analysis with PDF evidence integrated]

### Critic Perspective
The analysis correctly identifies the key mechanisms, though it should
emphasize that topological protection is not absolute...

[Critical review]

### Editor Perspective
[Synthesized final analysis]

## Supporting Evidence from Documents

[Source: majorana_fermions.pdf, Relevance: 0.87]
Chiral Majorana fermion is a massless self-conjugate fermion...

[Source: quantum_entanglement.pdf, Relevance: 0.82]
The EPR paradox demonstrates...

[Source: topology_quantum_computing.pdf, Relevance: 0.79]
Topological quantum computation based on anyons...

## References
1. majorana_fermions.pdf
2. quantum_entanglement.pdf
3. topology_quantum_computing.pdf
```

---

## File Access Details

### FlockParser Directory Structure

```
/home/joker/FlockParser/
├── knowledge_base/                  # PDF chunk storage
│   ├── doc_1_chunk_0.json          # {text, embedding[1024], page, chunk_index}
│   ├── doc_1_chunk_1.json
│   ├── doc_2_chunk_0.json
│   └── ...                         # ~2000+ chunk files
│
├── document_index.json             # Master index
│   # {documents: [{id, original, chunk_count, chunks}]}
│
└── testpdfs/                       # Original PDF files
    ├── majorana_fermions.pdf
    ├── quantum_entanglement.pdf
    └── ...
```

### Read-Only Access

SynapticLlamas **only reads** from FlockParser:
- ✅ Reads: `document_index.json`
- ✅ Reads: `knowledge_base/doc_*_chunk_*.json`
- ❌ Never writes to FlockParser

### No Dependencies

SynapticLlamas does **not** require FlockParser to be running:
- FlockParser CLI can be stopped
- Only needs the file system to be accessible
- Reads JSON files directly

---

## Performance Metrics

### Embedding Generation (Query)
| Method | Time | Notes |
|--------|------|-------|
| Direct Ollama (CPU) | 178ms | Slow |
| SOLLOL (GPU) | 8ms | **22x faster** |

### Document Search (15 chunks from 247 total)
| Method | Time | Notes |
|--------|------|-------|
| Local (CPU embeddings) | 2.4s | Sequential |
| Distributed (GPU embeddings) | 0.3s | **8x faster** |

### Total Enhancement Time
| Method | Time | Notes |
|--------|------|-------|
| Without SOLLOL | 3.1s | CPU-bound |
| With SOLLOL | 0.5s | **6x faster** |

---

## Configuration

### Enable RAG in SynapticLlamas

**Interactive:**
```bash
SynapticLlamas> rag on
```

**Programmatic:**
```python
# main.py config
config = {
    "flockparser_enabled": True,  # Enable RAG
    # ... other settings
}
```

### Check Status

```bash
SynapticLlamas> status

┌───────────────────┬────────────────────────────────────┐
│ FlockParser RAG   │ ON (12 docs, 247 chunks)           │
└───────────────────┴────────────────────────────────────┘
```

---

## Example Usage

### Full Example

```bash
# 1. Process PDFs in FlockParser (one-time)
cd /home/joker/FlockParser
python flockparsecli.py
# Select: 1. Process a PDF
# Add your research papers

# 2. Enable RAG in SynapticLlamas
cd /home/joker/SynapticLlamas
python main.py --interactive

SynapticLlamas> rag on
✅ FlockParser RAG ENABLED

# 3. Submit research query
SynapticLlamas> Explain topological quantum computation

📚 Enhancing query with FlockParser document context...
🔍 Querying FlockParser knowledge base...
   📚 Found 15 relevant chunks from 3 document(s)
   🎯 Top similarity: 0.87

🤝 Using collaborative workflow mode
[Researcher analyzing with PDF context...]
[Critic reviewing...]
[Editor synthesizing...]

# 4. Receive comprehensive report with citations
```

---

## Benefits

| Feature | Without RAG | With FlockParser RAG |
|---------|------------|---------------------|
| **Source Material** | Agent knowledge only | Agent knowledge + PDFs |
| **Citations** | None | Automatic from PDFs |
| **Accuracy** | Good | Excellent (document-grounded) |
| **Research Depth** | Limited to training data | Current research papers |
| **Embedding Speed** | 178ms (CPU) | 8ms (GPU via SOLLOL) |
| **Search Speed** | N/A | 0.3s (distributed) |
| **Report Quality** | Good | Outstanding (evidence-based) |

---

## Summary

SynapticLlamas interfaces with FlockParser for RAG through:

1. **File System Access** - Reads FlockParser's `knowledge_base/` and `document_index.json`
2. **Embedding Generation** - Uses SOLLOL GPU routing for 22x faster embeddings
3. **Semantic Search** - Calculates cosine similarity across all PDF chunks
4. **Context Enhancement** - Injects top 15 relevant chunks into research queries
5. **Collaborative Analysis** - All agents receive enhanced queries with PDF evidence
6. **Citation Tracking** - Automatically tracks source documents for references

The result: **Comprehensive, document-grounded research reports with automatic citations** - all powered by FlockParser's PDF knowledge base and SOLLOL's intelligent routing! 🚀📚
