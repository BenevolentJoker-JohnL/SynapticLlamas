"""
FlockParser Adapter for SynapticLlamas

Integrates FlockParser's document RAG capabilities into SynapticLlamas research workflow.
Allows research agents to pull relevant PDF content for enhanced, source-backed reports.

Features:
- Query FlockParser's knowledge base for relevant document chunks
- Inject PDF context into research prompts
- Track source documents for citations
- Adaptive context fitting based on token limits
"""
import json
import logging
import numpy as np
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import requests

logger = logging.getLogger(__name__)


class FlockParserAdapter:
    """
    Adapter for integrating FlockParser document retrieval into SynapticLlamas.

    This allows research agents to leverage parsed PDF content for comprehensive,
    source-backed research reports.
    """

    def __init__(
        self,
        flockparser_path: str = "/home/joker/FlockParser",
        embedding_model: str = "mxbai-embed-large",
        ollama_url: str = "http://localhost:11434",
        hybrid_router_sync=None,
        load_balancer=None
    ):
        """
        Initialize FlockParser adapter.

        Args:
            flockparser_path: Path to FlockParser installation
            embedding_model: Embedding model used by FlockParser
            ollama_url: URL of Ollama instance for embeddings
            hybrid_router_sync: Optional HybridRouterSync for distributed embeddings
            load_balancer: Optional SOLLOL LoadBalancer for intelligent routing
        """
        self.flockparser_path = Path(flockparser_path)
        self.knowledge_base_path = self.flockparser_path / "knowledge_base"
        self.document_index_path = self.flockparser_path / "document_index.json"
        self.embedding_model = embedding_model
        self.ollama_url = ollama_url

        # SOLLOL distributed routing support
        self.hybrid_router_sync = hybrid_router_sync
        self.load_balancer = load_balancer
        self.distributed_mode = hybrid_router_sync is not None

        # Check if FlockParser is available
        if not self.flockparser_path.exists():
            logger.warning(f"FlockParser not found at {flockparser_path}")
            self.available = False
        elif not self.document_index_path.exists():
            logger.info(f"FlockParser found but no documents indexed yet")
            self.available = True
        else:
            self.available = True
            doc_count = self._count_documents()
            mode_str = " (distributed mode)" if self.distributed_mode else ""
            logger.info(f"✅ FlockParser adapter initialized ({doc_count} documents){mode_str}")

    def _count_documents(self) -> int:
        """Count documents in FlockParser knowledge base."""
        try:
            with open(self.document_index_path, 'r') as f:
                index = json.load(f)
            return len(index.get('documents', []))
        except Exception as e:
            logger.debug(f"Could not count documents: {e}")
            return 0

    def _get_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for text using Ollama (with optional distributed routing).

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        try:
            # Use HybridRouter if available for intelligent routing
            if self.hybrid_router_sync:
                try:
                    result = self.hybrid_router_sync.generate_embedding(
                        model=self.embedding_model,
                        prompt=text
                    )
                    return result.get('embedding', []) if result else None
                except Exception as e:
                    logger.debug(f"HybridRouter embedding failed, falling back to direct: {e}")

            # Fallback to direct Ollama call
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={
                    "model": self.embedding_model,
                    "prompt": text
                },
                timeout=30
            )
            response.raise_for_status()
            embedding = response.json().get('embedding', [])
            return embedding if embedding else None
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            vec1 = np.array(vec1)
            vec2 = np.array(vec2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return 0.0

    def query_documents(
        self,
        query: str,
        top_k: int = 15,
        min_similarity: float = 0.3
    ) -> List[Dict]:
        """
        Query FlockParser knowledge base for relevant document chunks.

        Args:
            query: Search query
            top_k: Number of top results to return
            min_similarity: Minimum similarity threshold (0.0-1.0)

        Returns:
            List of relevant chunks with metadata:
            [
                {
                    "text": str,
                    "doc_name": str,
                    "similarity": float,
                    "doc_id": str
                },
                ...
            ]
        """
        if not self.available:
            logger.warning("FlockParser not available")
            return []

        if not self.document_index_path.exists():
            logger.info("No documents indexed in FlockParser yet")
            return []

        try:
            # Generate query embedding
            logger.info(f"🔍 Querying FlockParser knowledge base: '{query[:60]}...'")
            query_embedding = self._get_embedding(query)

            if not query_embedding:
                logger.error("Failed to generate query embedding")
                return []

            # Load document index
            with open(self.document_index_path, 'r') as f:
                index_data = json.load(f)

            documents = index_data.get('documents', [])
            if not documents:
                logger.info("No documents in knowledge base")
                return []

            # Collect all chunks with similarities
            chunks_with_similarity = []

            for doc in documents:
                for chunk_ref in doc.get('chunks', []):
                    try:
                        chunk_file = Path(chunk_ref['file'])
                        if chunk_file.exists():
                            with open(chunk_file, 'r') as f:
                                chunk_data = json.load(f)

                            chunk_embedding = chunk_data.get('embedding', [])
                            if chunk_embedding:
                                similarity = self._cosine_similarity(
                                    query_embedding,
                                    chunk_embedding
                                )

                                if similarity >= min_similarity:
                                    chunks_with_similarity.append({
                                        'text': chunk_data['text'],
                                        'doc_name': Path(doc['original']).name,
                                        'similarity': similarity,
                                        'doc_id': doc['id']
                                    })
                    except Exception as e:
                        logger.debug(f"Error processing chunk: {e}")

            # Sort by similarity and return top k
            chunks_with_similarity.sort(key=lambda x: x['similarity'], reverse=True)
            results = chunks_with_similarity[:top_k]

            # Group by document for logging
            doc_names = set(chunk['doc_name'] for chunk in results)
            logger.info(
                f"   📚 Found {len(results)} relevant chunks from {len(doc_names)} document(s)"
            )
            if results:
                logger.info(f"   🎯 Top similarity: {results[0]['similarity']:.3f}")

            return results

        except Exception as e:
            logger.error(f"Error querying FlockParser: {e}")
            return []

    def format_context_for_research(
        self,
        chunks: List[Dict],
        max_tokens: int = 2000
    ) -> Tuple[str, List[str]]:
        """
        Format retrieved chunks as context for research agents.

        Args:
            chunks: List of retrieved chunks
            max_tokens: Maximum tokens to use for context

        Returns:
            (formatted_context, source_documents)
        """
        if not chunks:
            return "", []

        def estimate_tokens(text: str) -> int:
            """Conservative token estimation: 1 token ≈ 3.5 chars."""
            return int(len(text) / 3.5)

        context_parts = []
        current_tokens = 0
        sources = set()
        chunks_used = 0

        for chunk in chunks:
            formatted = (
                f"[Source: {chunk['doc_name']}, Relevance: {chunk['similarity']:.2f}]\n"
                f"{chunk['text']}"
            )

            chunk_tokens = estimate_tokens(formatted)

            if current_tokens + chunk_tokens <= max_tokens:
                context_parts.append(formatted)
                current_tokens += chunk_tokens
                sources.add(chunk['doc_name'])
                chunks_used += 1
            else:
                break

        if context_parts:
            context = "\n\n---\n\n".join(context_parts)
            logger.info(
                f"   📄 Prepared context: {chunks_used} chunks, "
                f"{len(sources)} sources, ~{current_tokens} tokens"
            )
        else:
            context = ""

        return context, list(sources)

    def enhance_research_query(
        self,
        query: str,
        top_k: int = 15,
        max_context_tokens: int = 2000
    ) -> Tuple[str, List[str]]:
        """
        Enhance a research query with relevant document context.

        Args:
            query: Original research query
            top_k: Number of chunks to retrieve
            max_context_tokens: Max tokens for context

        Returns:
            (enhanced_query, source_documents)

        Example:
            query = "Explain quantum computing"
            enhanced, sources = adapter.enhance_research_query(query)
            # enhanced will include relevant PDF excerpts
            # sources = ["quantum_computing_paper.pdf", "introduction_to_qc.pdf"]
        """
        # Query FlockParser
        chunks = self.query_documents(query, top_k=top_k)

        if not chunks:
            logger.info("   No relevant documents found - using query as-is")
            return query, []

        # Format context
        context, sources = self.format_context_for_research(
            chunks,
            max_tokens=max_context_tokens
        )

        if not context:
            return query, []

        # Build enhanced query
        enhanced_query = f"""Research topic: {query}

RELEVANT DOCUMENT EXCERPTS:
{context}

---

Based on the above document excerpts and your knowledge, provide a comprehensive technical explanation of: {query}

IMPORTANT:
- Integrate information from the provided sources where relevant
- Add additional context and explanations beyond what's in the sources
- Cite specific findings from the documents when you use them
- Still provide comprehensive coverage even if sources are limited to certain aspects
"""

        logger.info(f"✅ Enhanced query with {len(sources)} source document(s)")

        return enhanced_query, sources

    def generate_document_report(
        self,
        query: str,
        agent_insights: List[Dict],
        top_k: int = 20,
        max_context_tokens: int = 3000
    ) -> Dict:
        """
        Generate a comprehensive report combining agent insights with document evidence.

        Args:
            query: Research query
            agent_insights: List of agent outputs (Researcher, Critic, Editor)
            top_k: Number of document chunks to retrieve
            max_context_tokens: Maximum tokens for document context

        Returns:
            {
                'report': str,  # Formatted markdown report
                'sources': List[str],  # Source documents cited
                'evidence_chunks': List[Dict],  # Retrieved evidence
                'agent_count': int
            }
        """
        logger.info(f"📝 Generating document-grounded report for: {query[:60]}...")

        # Query FlockParser for relevant evidence
        evidence_chunks = self.query_documents(query, top_k=top_k)

        # Format document evidence
        evidence_context, sources = self.format_context_for_research(
            evidence_chunks,
            max_tokens=max_context_tokens
        )

        # Build comprehensive report
        report_sections = []

        # Executive Summary
        report_sections.append("# Research Report\n")
        report_sections.append(f"**Query:** {query}\n")

        if sources:
            report_sections.append(f"**Sources:** {len(sources)} document(s)\n")
            report_sections.append(f"**Evidence Chunks:** {len(evidence_chunks)} relevant sections\n")

        # Agent Insights Section
        report_sections.append("\n## Analysis\n")

        for insight in agent_insights:
            agent_name = insight.get('agent', 'Unknown')
            data = insight.get('data', {})

            # Extract content from various formats
            if isinstance(data, dict):
                content = data.get('context', data.get('detailed_explanation', data.get('content', '')))
                key_facts = data.get('key_facts', [])
            else:
                content = str(data)
                key_facts = []

            if content:
                report_sections.append(f"### {agent_name} Perspective\n")
                report_sections.append(f"{content}\n")

                if key_facts:
                    report_sections.append("\n**Key Points:**\n")
                    for fact in key_facts:
                        report_sections.append(f"- {fact}\n")
                report_sections.append("\n")

        # Document Evidence Section
        if evidence_context:
            report_sections.append("\n## Supporting Evidence from Documents\n")
            report_sections.append(evidence_context)
            report_sections.append("\n")

        # Citations Section
        if sources:
            report_sections.append("\n## References\n")
            for i, source in enumerate(sources, 1):
                report_sections.append(f"{i}. {source}\n")

        report = "\n".join(report_sections)

        logger.info(f"✅ Report generated: {len(agent_insights)} agent insights, {len(sources)} sources")

        return {
            'report': report,
            'sources': sources,
            'evidence_chunks': evidence_chunks,
            'agent_count': len(agent_insights)
        }

    def get_statistics(self) -> Dict:
        """Get statistics about FlockParser knowledge base."""
        if not self.available or not self.document_index_path.exists():
            return {
                'available': False,
                'documents': 0,
                'chunks': 0
            }

        try:
            with open(self.document_index_path, 'r') as f:
                index_data = json.load(f)

            documents = index_data.get('documents', [])
            total_chunks = sum(len(doc.get('chunks', [])) for doc in documents)

            return {
                'available': True,
                'documents': len(documents),
                'chunks': total_chunks,
                'document_names': [Path(doc['original']).name for doc in documents]
            }
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {
                'available': False,
                'error': str(e)
            }


# Global instance
_adapter = None


def get_flockparser_adapter(
    flockparser_path: str = "/home/joker/FlockParser",
    hybrid_router_sync=None,
    load_balancer=None,
    **kwargs
) -> FlockParserAdapter:
    """
    Get or create global FlockParser adapter instance.

    Args:
        flockparser_path: Path to FlockParser installation
        hybrid_router_sync: Optional HybridRouterSync for distributed embeddings
        load_balancer: Optional SOLLOL LoadBalancer
        **kwargs: Additional arguments passed to FlockParserAdapter
    """
    global _adapter
    if _adapter is None:
        _adapter = FlockParserAdapter(
            flockparser_path,
            hybrid_router_sync=hybrid_router_sync,
            load_balancer=load_balancer,
            **kwargs
        )
    return _adapter


__all__ = ['FlockParserAdapter', 'get_flockparser_adapter']
