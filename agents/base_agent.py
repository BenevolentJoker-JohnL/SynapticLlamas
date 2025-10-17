from abc import ABC, abstractmethod
import requests
import json
import time
import sys
import os
import logging
import asyncio
import re
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_pipeline import standardize_to_json
from trustcall import trust_validator

logger = logging.getLogger(__name__)


def clean_broken_latex(text: str) -> str:
    """
    Clean up broken LaTeX notation that llama3.2 generates.

    Common issues:
    - Missing proper bracket notation |ψ⟩ appears as |psi
    - rangle appears as literal "rangle" instead of ⟩
    - sqrt() missing parentheses
    - LaTeX commands without backslashes
    """
    if not text:
        return text

    cleaned = text

    # Fix LaTeX bracket notation
    # |00rangle |11rangle → |00⟩ + |11⟩
    cleaned = re.sub(r'\|([0-9a-zA-Z_]+)rangle', r'|\1⟩', cleaned)

    # Fix common LaTeX commands that lost their backslashes
    # sqrt(1/2) is fine, but "sqrt(" without closing should have √
    cleaned = re.sub(r'\bsqrt\(([\d/]+)\)', r'√(\1)', cleaned)

    # Fix |psi → |ψ⟩, |phi → |φ⟩, etc.
    greek_letter_map = {
        'psi': 'ψ',
        'phi': 'φ',
        'alpha': 'α',
        'beta': 'β',
        'gamma': 'γ',
        'delta': 'δ',
        'epsilon': 'ε',
        'theta': 'θ',
        'lambda': 'λ',
        'mu': 'μ',
        'sigma': 'σ',
        'omega': 'ω',
        'rho': 'ρ',
    }

    # Replace |letterName with |Symbol⟩ (only in ket notation)
    for name, symbol in greek_letter_map.items():
        # |psi → |ψ⟩ (add closing bracket if missing)
        cleaned = re.sub(r'\|' + name + r'(?![\w])', r'|' + symbol + '⟩', cleaned, flags=re.IGNORECASE)

    # Fix literal "rangle" and "langle" that weren't caught
    cleaned = cleaned.replace('rangle', '⟩')
    cleaned = cleaned.replace('langle', '⟨')

    # Fix "00rangle |11rangle" → "|00⟩ + |11⟩" (add missing + operator)
    cleaned = re.sub(r'\|(\d+)⟩\s+\|(\d+)⟩', r'|\1⟩ + |\2⟩', cleaned)

    # Fix Unicode escape sequences for arrows
    cleaned = cleaned.replace('\\uparrow', '↑')
    cleaned = cleaned.replace('\\downarrow', '↓')
    cleaned = cleaned.replace('\\leftarrow', '←')
    cleaned = cleaned.replace('\\rightarrow', '→')
    cleaned = cleaned.replace('\\Uparrow', '⇑')
    cleaned = cleaned.replace('\\Downarrow', '⇓')

    # Normalize spacing
    cleaned = re.sub(r'[^\S\n]+', ' ', cleaned)  # Multiple spaces → single space
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)  # Multiple newlines → double newline

    return cleaned


def preprocess_llama32_response(raw_output: str, expected_schema: dict, agent_name: str) -> str:
    """
    Aggressive preprocessing for llama3.2 responses before TrustCall validation.

    llama3.2:3b on CPU often produces malformed JSON:
    - Wrapped in markdown code blocks
    - Literally copying schema examples ({"context": str})
    - Adding explanations before/after JSON
    - Mixing text and JSON

    This function:
    1. Strips all formatting (markdown, code blocks, extra text)
    2. Extracts actual content from the response
    3. Forces extracted content into the proper schema structure
    4. Returns clean JSON string ready for TrustCall validation

    Args:
        raw_output: Raw text output from llama3.2
        expected_schema: Expected JSON structure {field: type}
        agent_name: Agent name for logging

    Returns:
        Clean JSON string ready for TrustCall validation
    """
    logger.info(f"   🔧 {agent_name} - Preprocessing llama3.2 response (length: {len(raw_output)} chars)")

    # Step 1: Strip markdown code blocks
    cleaned = raw_output

    # Remove ```json ... ``` blocks and extract content
    json_block_match = re.search(r'```(?:json)?\s*(.*?)\s*```', cleaned, re.DOTALL)
    if json_block_match:
        cleaned = json_block_match.group(1)
        logger.debug(f"   📝 Stripped markdown code blocks")

    # Step 2: Try to parse as JSON first
    try:
        parsed = json.loads(cleaned)

        # Check if this is a literal schema copy (field values are Python type names)
        is_literal_schema = False
        if isinstance(parsed, dict):
            for field, value in parsed.items():
                if isinstance(value, str) and value in ['str', 'dict', 'list', 'int', 'float', 'bool']:
                    is_literal_schema = True
                    logger.warning(f"   ⚠️  Detected literal schema copy: {field} = '{value}'")
                    break

        # If it's valid JSON and NOT a literal schema copy, clean LaTeX and return it
        if not is_literal_schema:
            logger.info(f"   ✅ Valid JSON found (no literal schema)")
            # Clean broken LaTeX in string fields
            for field, value in parsed.items():
                if isinstance(value, str):
                    parsed[field] = clean_broken_latex(value)
            logger.info(f"   🧹 Cleaned broken LaTeX notation in JSON fields")
            return json.dumps(parsed)

        # Otherwise, fall through to content extraction
        logger.warning(f"   ⚠️  JSON is literal schema copy, extracting actual content")

    except json.JSONDecodeError:
        logger.debug(f"   ⚠️  Not valid JSON, attempting content extraction")

    # Step 3: Extract actual content from the response
    # Try to extract from JSON structure first (most reliable)
    extracted_content = None

    # Try to find and parse JSON object, then extract content field
    json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_output, re.DOTALL)
    if json_match:
        try:
            potential_json = json.loads(json_match.group(0))
            if isinstance(potential_json, dict):
                # Try to extract from content fields
                for key in ['context', 'detailed_explanation', 'story', 'summary', 'narrative']:
                    if key in potential_json and potential_json[key]:
                        value = potential_json[key]
                        # Make sure it's not a literal schema copy
                        if isinstance(value, str) and value not in ['str', 'dict', 'list'] and len(value) > 100:
                            # Clean LaTeX before using
                            extracted_content = clean_broken_latex(value)
                            logger.info(f"   📝 Extracted {len(extracted_content)} chars from JSON field '{key}'")
                            break
        except:
            pass

    # Fallback: use regex patterns if JSON extraction failed
    if not extracted_content:
        content_patterns = [
            # Pattern 1: Look for text after keywords
            r'(?:explanation|context|answer|response):\s*(.{100,})',
            # Pattern 2: Any substantial paragraph of text (allow citation markers [1], [2])
            r'\n\n([A-Z][^{}]{200,})',  # Removed \[\] from exclusion to allow citations
        ]

        for pattern in content_patterns:
            match = re.search(pattern, raw_output, re.DOTALL | re.IGNORECASE)
            if match:
                extracted_content = clean_broken_latex(match.group(1).strip())
                logger.info(f"   📝 Extracted content using regex pattern (length: {len(extracted_content)} chars)")
                break

    # If still no content, look for any text that's not JSON syntax
    if not extracted_content:
        # Remove all JSON syntax characters and see what's left
        text_only = re.sub(r'[{}\[\]":,]', ' ', raw_output)
        text_only = re.sub(r'\s+', ' ', text_only).strip()

        # Filter out schema keywords and type names
        schema_keywords = ['context', 'str', 'dict', 'list', 'int', 'float', 'bool', 'summary',
                          'detailed_explanation', 'story', 'examples', 'key_points']
        words = text_only.split()
        content_words = [w for w in words if w.lower() not in schema_keywords and len(w) > 2]

        if len(content_words) > 20:  # Need at least some substance
            extracted_content = ' '.join(content_words)
            logger.info(f"   📝 Extracted {len(content_words)} content words from text")

    # Step 4: Force content into expected schema structure
    if extracted_content and len(extracted_content) > 50:
        # Clean up broken LaTeX before forcing into schema
        cleaned_content = clean_broken_latex(extracted_content)
        logger.info(f"   🧹 Cleaned broken LaTeX notation")

        # Build proper JSON with extracted content
        forced_json = {}

        # Map content to appropriate schema field
        for field, field_type in expected_schema.items():
            if field_type == str:
                # For string fields, use the extracted content
                if field in ['context', 'detailed_explanation', 'story', 'summary', 'narrative']:
                    forced_json[field] = cleaned_content
                else:
                    # For other string fields, provide a reasonable default
                    forced_json[field] = f"[Extracted content for {field}]"

            elif field_type == list:
                # For list fields, provide empty list (TrustCall can request repair)
                forced_json[field] = []

            elif field_type == dict:
                # For dict fields, provide empty dict
                forced_json[field] = {}

            else:
                # For other types, provide None
                forced_json[field] = None

        logger.info(f"   ✅ Forced content into schema (content: {len(cleaned_content)} chars)")
        return json.dumps(forced_json)

    # Step 5: If all else fails, try to extract ANY JSON object from the response
    json_object_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw_output, re.DOTALL)
    if json_object_match:
        try:
            potential_json = json_object_match.group(0)
            parsed = json.loads(potential_json)
            logger.info(f"   ✅ Extracted JSON object from response")
            return json.dumps(parsed)
        except:
            pass

    # Last resort: return minimal valid JSON with error indicator
    logger.error(f"   ❌ Could not extract meaningful content from response")
    minimal_json = {}
    for field, field_type in expected_schema.items():
        if field_type == str:
            minimal_json[field] = "[Failed to extract content - see raw output]"
        elif field_type == list:
            minimal_json[field] = []
        elif field_type == dict:
            minimal_json[field] = {}
        else:
            minimal_json[field] = None

    return json.dumps(minimal_json)


def inject_citations_if_missing(
    prompt: str,
    validated_json: dict,
    agent_name: str,
    embedding_fn,
    min_similarity: float = 0.60
) -> dict:
    """
    Automatically inject citations into content when they're missing.

    Analyzes content sentences and compares them to source document chunks
    using embeddings. Inserts citation markers where similarity is high.

    Args:
        prompt: Original prompt containing RAG sources
        validated_json: Validated output JSON
        agent_name: Agent name for logging
        embedding_fn: Function to generate embeddings (takes text, returns list)
        min_similarity: Minimum similarity to insert citation (default: 0.60)

    Returns:
        Modified validated_json with citations inserted
    """
    try:
        # Extract content from validated_json
        content = ""
        content_key = None
        if isinstance(validated_json, dict):
            for key in ['context', 'story', 'detailed_explanation']:
                if key in validated_json:
                    content = validated_json[key]
                    content_key = key
                    break

        if not content or not content_key:
            return validated_json

        # Parse RAG sources from prompt
        sources = _parse_rag_sources(prompt)
        if not sources:
            return validated_json

        # Parse RAG chunks from prompt
        chunks = _parse_rag_chunks(prompt)
        if not chunks:
            logger.warning(f"   ⚠️  {agent_name} - Could not parse RAG chunks for auto-citation")
            return validated_json

        logger.info(f"   🔧 {agent_name} - Auto-injecting citations ({len(sources)} sources, {len(chunks)} chunks)")

        # Split content into sentences
        sentences = _split_into_sentences(content)
        logger.info(f"   📝 Analyzing {len(sentences)} sentences for citation opportunities")
        logger.debug(f"   📊 Content length: {len(content)} chars, first 100 chars: {content[:100]}")

        # Generate embeddings for source chunks (cache them)
        chunk_embeddings = []
        for i, chunk in enumerate(chunks):
            try:
                logger.debug(f"   🔹 Generating embedding for chunk {i+1}/{len(chunks)} (length: {len(chunk['text'])} chars)")
                embedding = embedding_fn(chunk['text'])
                if embedding:
                    chunk_embeddings.append({
                        'text': chunk['text'],
                        'source_idx': chunk['source_idx'],
                        'embedding': embedding
                    })
                    logger.debug(f"   ✅ Chunk {i+1} embedding generated ({len(embedding)} dimensions)")
                else:
                    logger.warning(f"   ⚠️  Chunk {i+1} embedding returned None")
            except Exception as e:
                logger.error(f"   ❌ Failed to embed chunk {i+1}: {e}")
                import traceback
                logger.debug(traceback.format_exc())

        if not chunk_embeddings:
            logger.warning(f"   ⚠️  {agent_name} - Could not generate chunk embeddings")
            return validated_json

        # Process each sentence
        modified_content = content
        citations_added = 0

        for sentence in sentences:
            # Skip sentences that already have citations
            if re.search(r'\[\d+\]', sentence):
                continue

            # Skip very short sentences (likely not substantive claims)
            if len(sentence.split()) < 5:
                continue

            # Generate embedding for sentence
            try:
                sentence_embedding = embedding_fn(sentence.strip())
                if not sentence_embedding:
                    continue

                # Find best matching source chunk
                best_similarity = 0.0
                best_source_idx = None

                for chunk_data in chunk_embeddings:
                    similarity = _cosine_similarity(sentence_embedding, chunk_data['embedding'])
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_source_idx = chunk_data['source_idx']

                # Insert citation if similarity is high enough
                if best_similarity >= min_similarity and best_source_idx is not None:
                    # Insert citation at end of sentence
                    citation_marker = f" [{best_source_idx}]"

                    # Find sentence in content and add citation
                    sentence_pattern = re.escape(sentence.strip())

                    # Add citation before period if sentence ends with one
                    if sentence.strip().endswith('.'):
                        modified_sentence = sentence.strip()[:-1] + citation_marker + '.'
                        modified_content = modified_content.replace(sentence.strip(), modified_sentence, 1)
                    else:
                        modified_sentence = sentence.strip() + citation_marker
                        modified_content = modified_content.replace(sentence.strip(), modified_sentence, 1)

                    citations_added += 1
                    logger.debug(f"   📎 Added [{best_source_idx}] (sim: {best_similarity:.2f}): {sentence[:60]}...")

            except Exception as e:
                logger.debug(f"Failed to process sentence: {e}")
                continue

        # Update validated_json with modified content
        if citations_added > 0:
            validated_json[content_key] = modified_content
            logger.info(f"   ✅ {agent_name} - Auto-injected {citations_added} citations")
        else:
            logger.warning(f"   ⚠️  {agent_name} - No suitable citation opportunities found (all sentences < {min_similarity:.2f} similarity)")

        return validated_json

    except Exception as e:
        logger.error(f"   ❌ {agent_name} - Auto-citation failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return validated_json


def _parse_rag_sources(prompt: str) -> list:
    """Extract source list from RAG-enhanced prompt."""
    try:
        match = re.search(r'AVAILABLE SOURCES FOR CITATION:\n((?:\[\d+\] .+\n?)+)', prompt)
        if match:
            sources_text = match.group(1)
            sources = []
            for line in sources_text.strip().split('\n'):
                if line.strip():
                    sources.append(line.strip())
            return sources
    except Exception as e:
        logger.debug(f"Failed to parse sources: {e}")
    return []


def _parse_rag_chunks(prompt: str) -> list:
    """Extract document chunks from RAG-enhanced prompt."""
    try:
        match = re.search(r'RELEVANT DOCUMENT EXCERPTS:\n(.*?)\n\nAVAILABLE SOURCES FOR CITATION:', prompt, re.DOTALL)
        if match:
            excerpts_text = match.group(1)
            chunks = []

            # Split by separator
            chunk_texts = excerpts_text.split('\n\n---\n\n')

            for chunk_text in chunk_texts:
                # Extract source name
                source_match = re.search(r'\[Source: (.+?), Relevance: [\d.]+\]', chunk_text)
                if source_match:
                    source_name = source_match.group(1)
                    # Remove the metadata line to get just the text
                    text = re.sub(r'\[Source: .+?\]\n', '', chunk_text).strip()

                    # Find source index
                    source_idx = None
                    sources = _parse_rag_sources(prompt)
                    for i, source_line in enumerate(sources, 1):
                        if source_name in source_line:
                            source_idx = i
                            break

                    if source_idx:
                        chunks.append({
                            'text': text,
                            'source_idx': source_idx,
                            'source_name': source_name
                        })

            return chunks
    except Exception as e:
        logger.debug(f"Failed to parse chunks: {e}")
    return []


def _split_into_sentences(text: str) -> list:
    """Split text into sentences (simple approach)."""
    # Simple sentence splitter (handles most cases)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s for s in sentences if s.strip()]


def _cosine_similarity(vec1: list, vec2: list) -> float:
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
        logger.debug(f"Error calculating similarity: {e}")
        return 0.0


def check_citation_compliance(prompt: str, validated_json: dict, agent_name: str, embedding_fn=None) -> dict:
    """
    Check if output contains citations when RAG sources were provided.
    If missing and embedding_fn provided, automatically inject citations.

    Args:
        prompt: The original prompt sent to the LLM
        validated_json: The validated JSON output
        agent_name: Name of the agent for logging
        embedding_fn: Optional function to generate embeddings for auto-citation

    Returns:
        validated_json (potentially modified with auto-injected citations)
    """
    # Check if this was a RAG-enhanced prompt
    if "AVAILABLE SOURCES FOR CITATION" not in prompt:
        return validated_json  # No RAG sources, no citation expected

    # Extract the content from various possible fields
    content = ""
    if isinstance(validated_json, dict):
        content = validated_json.get('context',
                  validated_json.get('story',
                  validated_json.get('detailed_explanation', '')))

    if not content:
        return validated_json  # No content to check

    # Check for citation markers [1], [2], [3], etc.
    citation_pattern = r'\[\d+\]'
    citations_found = re.findall(citation_pattern, str(content))

    if not citations_found:
        logger.warning(f"⚠️  {agent_name} - RAG sources provided but NO CITATIONS in output")
        logger.warning(f"   📋 Citation compliance: 0% (expected [1], [2], etc.)")

        # Attempt auto-injection if embedding function available
        if embedding_fn:
            logger.info(f"   🔧 {agent_name} - Attempting automatic citation injection...")
            validated_json = inject_citations_if_missing(
                prompt,
                validated_json,
                agent_name,
                embedding_fn,
                min_similarity=0.60
            )
        else:
            logger.warning(f"   ⚠️  {agent_name} - No embedding function available for auto-citation")
    else:
        unique_citations = set(citations_found)
        logger.info(f"✅ {agent_name} - Citation compliance: {len(unique_citations)} unique citation(s) found")

    return validated_json


class BaseAgent(ABC):
    def __init__(self, name, model="llama3.2", ollama_url=None, timeout=300, priority=5):
        self.name = name
        self.model = model

        # Use SOLLOL by default if no URL specified
        if ollama_url is None:
            from sollol_adapter import get_adapter
            adapter = get_adapter()
            ollama_url = adapter.get_ollama_url()
            self.priority = adapter.get_priority_for_agent(name)
        else:
            self.priority = priority

        self.ollama_url = ollama_url
        self.execution_time = 0
        self.timeout = timeout  # Default 5 minutes for CPU inference
        self.expected_schema = {}  # Subclasses can define expected JSON schema

    def call_ollama(self, prompt, system_prompt=None, force_json=True, use_trustcall=True):
        """Call Ollama API with the given prompt using SOLLOL intelligent routing."""
        start_time = time.time()

        # Debug: Check what routing is available
        has_hybrid = hasattr(self, '_hybrid_router_sync') and self._hybrid_router_sync is not None
        has_lb = hasattr(self, '_load_balancer') and self._load_balancer is not None
        logger.info(f"🔍 {self.name}: has_hybrid={has_hybrid}, has_lb={has_lb}, model={self.model}")

        # Check if HybridRouter sync wrapper is available for RPC sharding
        if hasattr(self, '_hybrid_router_sync') and self._hybrid_router_sync is not None:
            try:
                logger.info(f"🔀 Using HybridRouter for {self.model}")

                # Convert to messages format
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                # Call sync wrapper (runs in background thread, no event loop issues)
                response = self._hybrid_router_sync.route_request(
                    model=self.model,
                    messages=messages,
                    stream=False,
                    timeout=self.timeout
                )

                self.execution_time = time.time() - start_time
                logger.info(f"✅ {self.name} completed via HybridRouter in {self.execution_time:.2f}s")

                # Extract content from response
                if isinstance(response, dict):
                    if 'message' in response:
                        raw_output = response['message'].get('content', '')
                    elif 'response' in response:
                        raw_output = response['response']
                    elif 'content' in response:
                        raw_output = response['content']
                    else:
                        raw_output = str(response)
                else:
                    raw_output = str(response)

                # Use TrustCall validation if enabled and schema defined
                if use_trustcall and force_json and hasattr(self, 'expected_schema') and self.expected_schema:
                    # Preprocess llama3.2 responses BEFORE TrustCall validation
                    if 'llama3.2' in self.model.lower():
                        logger.info(f"   🔧 {self.name} - Applying llama3.2 preprocessing")
                        preprocessed_output = preprocess_llama32_response(
                            raw_output,
                            self.expected_schema,
                            self.name
                        )
                    else:
                        preprocessed_output = raw_output

                    # Create repair function that can call LLM again via HybridRouter
                    def repair_fn(repair_prompt):
                        try:
                            repair_messages = [{"role": "user", "content": repair_prompt}]
                            repair_response = self._hybrid_router_sync.route_request(
                                model=self.model,
                                messages=repair_messages,
                                stream=False,
                                timeout=self.timeout
                            )
                            if isinstance(repair_response, dict):
                                if 'message' in repair_response:
                                    return repair_response['message'].get('content', '{}')
                                elif 'response' in repair_response:
                                    return repair_response['response']
                                elif 'content' in repair_response:
                                    return repair_response['content']
                            return "{}"
                        except Exception as e:
                            logger.error(f"HybridRouter repair call failed: {e}")
                            return "{}"

                    # Validate and repair using TrustCall (with preprocessed output)
                    validated_json = trust_validator.validate_and_repair(
                        preprocessed_output,
                        self.expected_schema,
                        repair_fn,
                        self.name
                    )

                    # Create embedding function for auto-citation
                    # Note: Always use direct Ollama API for embeddings (HybridRouter doesn't support embeddings)
                    def embedding_fn(text):
                        try:
                            embed_response = requests.post(
                                "http://localhost:11434/api/embeddings",
                                json={
                                    "model": "mxbai-embed-large",
                                    "prompt": text
                                },
                                timeout=30
                            )
                            embed_response.raise_for_status()
                            result = embed_response.json()
                            embedding = result.get('embedding', [])
                            if embedding:
                                return embedding
                            logger.warning(f"Embedding API returned empty result: {result}")
                            return None
                        except Exception as e:
                            logger.error(f"Embedding generation failed: {e}")
                            import traceback
                            logger.error(traceback.format_exc())
                            return None

                    # Check citation compliance if RAG was used (with auto-injection)
                    validated_json = check_citation_compliance(prompt, validated_json, self.name, embedding_fn)

                    return {
                        "agent": self.name,
                        "status": "success",
                        "format": "json",
                        "data": validated_json
                    }
                else:
                    # Fallback to old standardization
                    return {
                        "agent": self.name,
                        "status": "success",
                        "format": "json" if force_json else "text",
                        "data": standardize_to_json(self.name, raw_output) if force_json else raw_output
                    }
            except Exception as e:
                logger.error(f"❌ HybridRouter failed for {self.name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Fall through to regular Ollama call

        # Build payload - try with format: json first
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "num_predict": 4096  # Increase token limit for complete answers (default ~2048)
            }
        }

        if force_json:
            payload["format"] = "json"

        if system_prompt:
            payload["system"] = system_prompt

        # Get SOLLOL routing decision if using load balancer
        routing_decision = None
        routing_metadata = {}

        # Check if we're in distributed mode with SOLLOL
        if hasattr(self, '_load_balancer') and self._load_balancer is not None:
            try:
                routing_decision = self._load_balancer.route_request(
                    payload=payload,
                    agent_name=self.name,
                    priority=self.priority
                )
                # Use the node URL from routing decision
                url = f"{routing_decision.node.url}/api/generate"
                routing_metadata = self._load_balancer.get_routing_metadata(routing_decision)

                routing_msg = (
                    f"🎯 SOLLOL routed {self.name} to {routing_decision.node.url} "
                    f"(score: {routing_decision.decision_score:.1f})"
                )
                logger.info(routing_msg)
                # Also print to stdout for CLI visibility
                print(f"   {routing_msg}")
            except Exception as e:
                logger.error(f"❌ SOLLOL routing failed, using default URL: {e}")
                url = f"{self.ollama_url}/api/generate"
        else:
            url = f"{self.ollama_url}/api/generate"
            logger.info(f"📍 {self.name} using default URL: {self.ollama_url}")

        try:
            logger.info(f"📤 {self.name} sending request to {url} (timeout: {self.timeout}s)")
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            self.execution_time = time.time() - start_time
            completion_msg = f"✅ {self.name} completed in {self.execution_time:.2f}s"
            logger.info(completion_msg)
            # Also print to stdout for CLI visibility
            print(f"   {completion_msg}")
            raw_output = result.get("response", "")

            # Record performance for SOLLOL adaptive learning
            if routing_decision and hasattr(self, '_load_balancer'):
                actual_duration_ms = self.execution_time * 1000
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=actual_duration_ms,
                    success=True,
                    error=None
                )

            # Use TrustCall validation and repair if enabled and schema defined
            if use_trustcall and force_json and self.expected_schema:
                # Preprocess llama3.2 responses BEFORE TrustCall validation
                if 'llama3.2' in self.model.lower():
                    logger.info(f"   🔧 {self.name} - Applying llama3.2 preprocessing")
                    preprocessed_output = preprocess_llama32_response(
                        raw_output,
                        self.expected_schema,
                        self.name
                    )
                else:
                    preprocessed_output = raw_output

                # Create repair function that can call LLM again
                def repair_fn(repair_prompt):
                    repair_payload = {
                        "model": self.model,
                        "prompt": repair_prompt,
                        "stream": False,
                        "options": {
                            "num_predict": 4096  # Same token limit as main request
                        }
                    }
                    try:
                        repair_response = requests.post(url, json=repair_payload, timeout=self.timeout)
                        repair_response.raise_for_status()
                        repair_result = repair_response.json()
                        return repair_result.get("response", "")
                    except Exception as e:
                        logger.error(f"Repair call failed: {e}")
                        return "{}"

                # Validate and repair using TrustCall (with preprocessed output)
                validated_json = trust_validator.validate_and_repair(
                    preprocessed_output,
                    self.expected_schema,
                    repair_fn,
                    self.name
                )

                # Create embedding function for auto-citation
                def embedding_fn(text):
                    try:
                        embed_response = requests.post(
                            f"{self.ollama_url}/api/embeddings",
                            json={
                                "model": "mxbai-embed-large",
                                "prompt": text
                            },
                            timeout=30
                        )
                        embed_response.raise_for_status()
                        result = embed_response.json()
                        embedding = result.get('embedding', [])
                        if embedding:
                            return embedding
                        logger.warning(f"Embedding API returned empty result: {result}")
                        return None
                    except Exception as e:
                        logger.error(f"Embedding generation failed: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                        return None

                # Check citation compliance if RAG was used (with auto-injection)
                validated_json = check_citation_compliance(prompt, validated_json, self.name, embedding_fn)

                # Add SOLLOL routing metadata
                if routing_metadata:
                    validated_json.update(routing_metadata)

                return validated_json
            else:
                # Fallback to old standardization
                standardized = standardize_to_json(self.name, raw_output)

                # Add SOLLOL routing metadata
                if routing_metadata:
                    standardized.update(routing_metadata)

                return standardized

        except requests.exceptions.Timeout as e:
            elapsed = time.time() - start_time
            logger.error(f"⏱️ TIMEOUT: {self.name} request to {url} timed out after {elapsed:.2f}s (limit: {self.timeout}s)")

            # Record failure for SOLLOL
            if routing_decision and hasattr(self, '_load_balancer'):
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=elapsed * 1000,
                    success=False,
                    error=f"Timeout after {elapsed:.2f}s"
                )

            self.execution_time = elapsed
            return {
                "agent": self.name,
                "status": "error",
                "format": "text",
                "data": {"error": f"Request timed out after {elapsed:.2f}s"}
            }

        except requests.exceptions.ConnectionError as e:
            elapsed = time.time() - start_time
            logger.error(f"🔌 CONNECTION ERROR: {self.name} could not connect to {url}: {e}")

            # Record failure for SOLLOL
            if routing_decision and hasattr(self, '_load_balancer'):
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=elapsed * 1000,
                    success=False,
                    error=f"Connection error: {str(e)}"
                )

            self.execution_time = elapsed
            return {
                "agent": self.name,
                "status": "error",
                "format": "text",
                "data": {"error": f"Connection error: {str(e)}"}
            }

        except requests.exceptions.HTTPError as e:
            # Record failure for SOLLOL
            if routing_decision and hasattr(self, '_load_balancer'):
                actual_duration_ms = (time.time() - start_time) * 1000
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=actual_duration_ms,
                    success=False,
                    error=str(e)
                )

            # If format: json not supported, retry without it
            if force_json and "format" in payload:
                logger.warning(f"{self.name}: Model may not support format parameter, retrying without it")
                payload.pop("format", None)
                try:
                    response = requests.post(url, json=payload, timeout=self.timeout)
                    response.raise_for_status()
                    result = response.json()
                    self.execution_time = time.time() - start_time
                    raw_output = result.get("response", "")
                    standardized = standardize_to_json(self.name, raw_output)

                    # Add routing metadata
                    if routing_metadata:
                        standardized.update(routing_metadata)

                    return standardized
                except Exception as retry_error:
                    self.execution_time = time.time() - start_time
                    error_response = {
                        "agent": self.name,
                        "status": "error",
                        "format": "text",
                        "data": {"error": str(retry_error)}
                    }

                    # Add routing metadata even on error
                    if routing_metadata:
                        error_response.update(routing_metadata)

                    return error_response
            else:
                self.execution_time = time.time() - start_time
                return {
                    "agent": self.name,
                    "status": "error",
                    "format": "text",
                    "data": {"error": str(e)}
                }
        except Exception as e:
            self.execution_time = time.time() - start_time
            return {
                "agent": self.name,
                "status": "error",
                "format": "text",
                "data": {"error": str(e)}
            }

    @abstractmethod
    def process(self, input_data):
        """Process input data and return standardized JSON output."""
        pass

    def get_metrics(self):
        """Return performance metrics."""
        return {
            "agent": self.name,
            "execution_time": round(self.execution_time, 2),
            "model": self.model
        }
