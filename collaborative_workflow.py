import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from agents.researcher import Researcher
from agents.critic import Critic
from agents.editor import Editor
from json_pipeline import validate_json_output
from quality_assurance import ASTQualityVoting
from json_to_markdown import json_to_markdown
import json

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    """Message passed between agents."""
    agent_name: str
    content: Dict
    iteration: int = 0
    metadata: Dict = field(default_factory=dict)


class CollaborativeWorkflow:
    """
    Multi-agent collaboration with sequential processing and feedback loops.
    Supports distributed acceleration for parallel refinement and multi-node execution.

    Workflow:
    1. Researcher → initial research
    2. Critic → reviews research, provides feedback
    3. Researcher → refines based on feedback (optional, can be parallelized)
    4. Editor → synthesizes everything into final output
    """

    def __init__(self, model: str = "llama3.2", max_refinement_rounds: int = 1,
                 distributed: bool = False, node_urls: List[str] = None, timeout: int = 300,
                 enable_ast_voting: bool = False, quality_threshold: float = 0.7,
                 max_quality_retries: int = 2):
        """
        Initialize collaborative workflow.

        Args:
            model: Ollama model to use
            max_refinement_rounds: Number of refinement iterations
            distributed: Use distributed nodes for acceleration
            node_urls: List of Ollama node URLs for distribution
            timeout: Inference timeout in seconds
            enable_ast_voting: Enable AST quality voting
            quality_threshold: Minimum quality score to pass (0.0-1.0)
            max_quality_retries: Maximum re-refinement attempts for quality
        """
        self.model = model
        self.max_refinement_rounds = max_refinement_rounds
        self.conversation_history: List[AgentMessage] = []
        self.distributed = distributed
        self.node_urls = node_urls or ["http://localhost:11434"]
        self.timeout = timeout
        self.enable_ast_voting = enable_ast_voting

        if enable_ast_voting:
            self.ast_voting = ASTQualityVoting(
                model=model,
                threshold=quality_threshold,
                max_retries=max_quality_retries,
                timeout=timeout
            )
        else:
            self.ast_voting = None

    def run(self, input_query: str, ollama_url: str = "http://localhost:11434") -> Dict:
        """
        Execute collaborative workflow.

        Args:
            input_query: User's input query
            ollama_url: Ollama instance URL

        Returns:
            Final synthesized output with full conversation history
        """
        import time

        logger.info("🤝 Starting collaborative workflow")
        self.conversation_history = []
        phase_times = []

        # Initialize agents
        researcher = Researcher(self.model, timeout=self.timeout)
        critic = Critic(self.model, timeout=self.timeout)
        editor = Editor(self.model, timeout=self.timeout)

        # Set Ollama URL for all agents
        researcher.ollama_url = ollama_url
        critic.ollama_url = ollama_url
        editor.ollama_url = ollama_url

        # PHASE 1: Initial Research
        logger.info("📚 Phase 1: Researcher - Initial research")
        phase_start = time.time()
        research_output = researcher.process(input_query)
        phase_1_time = time.time() - phase_start

        research_msg = AgentMessage(
            agent_name="Researcher",
            content=research_output,
            iteration=0,
            metadata={"phase": "initial_research"}
        )
        self.conversation_history.append(research_msg)
        phase_times.append(("Phase 1: Initial Research", phase_1_time))

        logger.info(f"✅ Researcher completed (iteration 0) - {phase_1_time:.2f}s")

        # PHASE 2: Critique and Feedback
        logger.info("🔍 Phase 2: Critic - Review and feedback")
        phase_start = time.time()

        critique_prompt = self._build_critique_prompt(input_query, research_output)
        critic_output = critic.process(critique_prompt)
        phase_2_time = time.time() - phase_start

        critic_msg = AgentMessage(
            agent_name="Critic",
            content=critic_output,
            iteration=0,
            metadata={"phase": "critique"}
        )
        self.conversation_history.append(critic_msg)
        phase_times.append(("Phase 2: Critique", phase_2_time))

        logger.info(f"✅ Critic completed - {phase_2_time:.2f}s")

        # PHASE 3: Refinement Loop (optional)
        refined_research = research_output

        if self.max_refinement_rounds > 0:
            if self.distributed and len(self.node_urls) > 1:
                # DISTRIBUTED REFINEMENT: Run multiple refinement attempts in parallel
                logger.info(f"🚀 Phase 3: Distributed Refinement ({len(self.node_urls)} nodes)")
                phase_start = time.time()
                refined_research = self._distributed_refinement(
                    input_query,
                    research_output,
                    critic_output,
                    researcher
                )
                phase_3_time = time.time() - phase_start
                phase_times.append(("Phase 3: Distributed Refinement", phase_3_time))
            else:
                # SEQUENTIAL REFINEMENT: Traditional sequential approach
                for iteration in range(1, self.max_refinement_rounds + 1):
                    logger.info(f"🔄 Phase 3: Researcher - Refinement round {iteration}")
                    phase_start = time.time()

                    refinement_prompt = self._build_refinement_prompt(
                        input_query,
                        refined_research,
                        critic_output
                    )

                    refined_research = researcher.process(refinement_prompt)
                    refinement_time = time.time() - phase_start

                    refinement_msg = AgentMessage(
                        agent_name="Researcher",
                        content=refined_research,
                        iteration=iteration,
                        metadata={"phase": "refinement"}
                    )
                    self.conversation_history.append(refinement_msg)
                    phase_times.append((f"Phase 3: Refinement {iteration}", refinement_time))

                    logger.info(f"✅ Researcher refinement {iteration} completed - {refinement_time:.2f}s")

        # PHASE 4: Final Synthesis
        logger.info("✨ Phase 4: Editor - Final synthesis")
        phase_start = time.time()

        synthesis_prompt = self._build_synthesis_prompt(
            input_query,
            refined_research,
            critic_output
        )

        final_output = editor.process(synthesis_prompt)
        phase_4_time = time.time() - phase_start

        final_msg = AgentMessage(
            agent_name="Editor",
            content=final_output,
            iteration=0,
            metadata={"phase": "final_synthesis"}
        )
        self.conversation_history.append(final_msg)
        phase_times.append(("Phase 4: Final Synthesis", phase_4_time))

        logger.info(f"✅ Editor completed - {phase_4_time:.2f}s")

        # Convert JSON to markdown
        markdown_content = json_to_markdown(final_output)

        # PHASE 5: AST Quality Voting (if enabled)
        quality_retries = 0
        quality_scores = []
        quality_passed = True

        if self.enable_ast_voting and self.ast_voting:
            logger.info("🗳️  Phase 5: AST Quality Voting")

            while quality_retries < self.ast_voting.max_retries:
                phase_start = time.time()

                # Evaluate quality
                passed, aggregate_score, scores = self.ast_voting.evaluate_quality(
                    input_query,
                    markdown_content,
                    ollama_url
                )
                quality_scores = scores
                phase_5_time = time.time() - phase_start

                if passed:
                    logger.info(f"✅ Quality voting PASSED - {aggregate_score:.2f}/{self.ast_voting.threshold:.2f}")
                    phase_times.append(("Phase 5: Quality Voting", phase_5_time))
                    quality_passed = True
                    break
                else:
                    quality_retries += 1
                    logger.warning(f"❌ Quality voting FAILED - Retry {quality_retries}/{self.ast_voting.max_retries}")
                    phase_times.append((f"Phase 5: Quality Voting (Attempt {quality_retries})", phase_5_time))

                    if quality_retries >= self.ast_voting.max_retries:
                        logger.warning(f"⚠️  Max quality retries reached - accepting current output")
                        quality_passed = False
                        break

                    # Generate improvement feedback
                    logger.info("🔄 Phase 5.1: Quality-based Re-refinement")
                    phase_start = time.time()

                    feedback = self.ast_voting.generate_improvement_feedback(
                        input_query,
                        markdown_content,
                        scores
                    )

                    # Editor re-refines based on quality feedback
                    improved_output = editor.process(feedback)
                    markdown_content = json_to_markdown(improved_output)

                    # Track re-refinement
                    rerefinement_msg = AgentMessage(
                        agent_name="Editor",
                        content=improved_output,
                        iteration=quality_retries,
                        metadata={"phase": "quality_rerefinement", "score": aggregate_score}
                    )
                    self.conversation_history.append(rerefinement_msg)

                    rerefinement_time = time.time() - phase_start
                    phase_times.append((f"Phase 5.1: Re-refinement {quality_retries}", rerefinement_time))
                    logger.info(f"✅ Re-refinement {quality_retries} completed - {rerefinement_time:.2f}s")

        # Calculate total time
        total_workflow_time = sum(t for _, t in phase_times)

        return {
            "final_output": markdown_content,
            "conversation_history": [self._serialize_message(msg) for msg in self.conversation_history],
            "workflow_summary": self._generate_summary(),
            "phase_timings": phase_times,
            "total_workflow_time": total_workflow_time,
            "quality_scores": [
                {
                    "agent": s.agent_name,
                    "score": s.score,
                    "reasoning": s.reasoning,
                    "issues": s.issues
                } for s in quality_scores
            ] if quality_scores else None,
            "quality_passed": quality_passed
        }

    def _build_critique_prompt(self, original_query: str, research_output: Dict) -> str:
        """Build prompt for critic to review researcher's work."""
        research_content = self._extract_content(research_output)

        return f"""Original Query: {original_query}

Researcher's Output:
{research_content}

Your task as a Critic:
1. Identify any factual errors or misleading information
2. Point out gaps in coverage or missing important aspects
3. Suggest improvements and additional areas to explore
4. Rate the quality and completeness

Provide your critique in a constructive manner."""

    def _build_refinement_prompt(self, original_query: str,
                                  research_output: Dict,
                                  critic_output: Dict) -> str:
        """Build prompt for researcher to refine based on feedback."""
        research_content = self._extract_content(research_output)
        critique_content = self._extract_content(critic_output)

        return f"""Original Query: {original_query}

Your Previous Research:
{research_content}

Critic's Feedback:
{critique_content}

Your task as a Researcher:
1. Address the issues raised by the Critic
2. Fill in the gaps identified
3. Improve the accuracy and completeness
4. Maintain your research focus while incorporating feedback

Provide an improved, refined version of your research."""

    def _build_synthesis_prompt(self, original_query: str,
                                 research_output: Dict,
                                 critic_output: Dict) -> str:
        """Build prompt for editor to synthesize final output."""
        research_content = self._extract_content(research_output)
        critique_content = self._extract_content(critic_output)

        return f"""You must answer this question: {original_query}

Research findings:
{research_content}

Critic's review:
{critique_content}

Create a comprehensive JSON structure with:
- summary: Brief 1-2 sentence overview answering the query
- key_points: List of 5-7 essential facts/concepts (be specific and detailed)
- detailed_explanation: Full, thorough explanation covering:
  * Underlying mechanisms/physics/theory
  * How it works in detail
  * Important context and background
  * Address all aspects of the query
- examples: List of 3-5 concrete, specific real-world examples
- practical_applications: List of 3-5 real-world applications, use cases, or implications

Incorporate the critic's feedback to ensure completeness and accuracy.
Be comprehensive, detailed, and thorough - not superficial.

Output valid JSON now:"""

    def _distributed_refinement(self, input_query: str, research_output: Dict,
                                 critic_output: Dict, researcher) -> Dict:
        """
        Run multiple refinement attempts in parallel across nodes, then pick best.

        Strategy:
        1. Generate N different refinement prompts (with variation)
        2. Execute them in parallel on different nodes
        3. Have critic evaluate all refinements
        4. Select the best one
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Generate varied refinement prompts
        num_variations = min(self.max_refinement_rounds, len(self.node_urls))
        refinement_prompts = []

        for i in range(num_variations):
            prompt = self._build_refinement_prompt_with_variation(
                input_query,
                research_output,
                critic_output,
                variation_index=i
            )
            refinement_prompts.append(prompt)

        # Execute refinements in parallel on different nodes
        logger.info(f"🔀 Running {num_variations} parallel refinement attempts")

        refinements = []
        with ThreadPoolExecutor(max_workers=len(self.node_urls)) as executor:
            # Create separate researcher instances for each node
            futures = []
            for i, (prompt, node_url) in enumerate(zip(refinement_prompts, self.node_urls[:num_variations])):
                # Create new researcher for this node
                node_researcher = Researcher(self.model, timeout=self.timeout)
                node_researcher.ollama_url = node_url

                future = executor.submit(node_researcher.process, prompt)
                futures.append((future, i, node_url))

            # Collect results
            for future, idx, node_url in futures:
                try:
                    result = future.result()
                    refinements.append({
                        'index': idx,
                        'node': node_url,
                        'output': result
                    })

                    refinement_msg = AgentMessage(
                        agent_name=f"Researcher-Node{idx}",
                        content=result,
                        iteration=idx,
                        metadata={"phase": "parallel_refinement", "node": node_url}
                    )
                    self.conversation_history.append(refinement_msg)

                    logger.info(f"✅ Refinement {idx} completed on {node_url}")
                except Exception as e:
                    logger.error(f"❌ Refinement {idx} failed: {e}")

        # If only one refinement, return it
        if len(refinements) == 1:
            return refinements[0]['output']

        # Otherwise, select the best one
        logger.info(f"🎯 Selecting best refinement from {len(refinements)} candidates")
        best_refinement = self._select_best_refinement(refinements, input_query)

        return best_refinement

    def _build_refinement_prompt_with_variation(self, original_query: str,
                                                 research_output: Dict,
                                                 critic_output: Dict,
                                                 variation_index: int) -> str:
        """Build refinement prompt with slight variation to explore different approaches."""
        research_content = self._extract_content(research_output)
        critique_content = self._extract_content(critic_output)

        variation_instructions = [
            "Focus on addressing the most critical issues first.",
            "Prioritize filling in the gaps identified by the critic.",
            "Emphasize improving accuracy and fact-checking.",
            "Take a different angle or perspective on the topic.",
            "Expand on areas that were underdeveloped."
        ]

        variation = variation_instructions[variation_index % len(variation_instructions)]

        return f"""Original Query: {original_query}

Your Previous Research:
{research_content}

Critic's Feedback:
{critique_content}

Your task as a Researcher:
1. Address the issues raised by the Critic
2. Fill in the gaps identified
3. Improve the accuracy and completeness
4. {variation}

Provide an improved, refined version of your research."""

    def _select_best_refinement(self, refinements: List[Dict], original_query: str) -> Dict:
        """
        Select the best refinement from parallel attempts.
        Uses a simple heuristic or could use another LLM call.
        """
        # For now, use a simple heuristic: longest content = most thorough
        # In production, you could have the Critic evaluate each one

        best = max(refinements, key=lambda x: len(self._extract_content(x['output'])))

        logger.info(f"🏆 Selected refinement {best['index']} from {best['node']}")

        return best['output']

    def _extract_content(self, agent_output: Dict) -> str:
        """Extract readable content from agent JSON output."""
        if isinstance(agent_output, dict):
            if "data" in agent_output:
                data = agent_output["data"]
                if isinstance(data, dict):
                    # Pretty print the data
                    return json.dumps(data, indent=2)
                else:
                    return str(data)
            else:
                return json.dumps(agent_output, indent=2)
        return str(agent_output)

    def _extract_markdown_content(self, agent_output: Dict) -> str:
        """Extract pure markdown content from editor's output."""
        if isinstance(agent_output, dict):
            # Try to get the actual text content from the data field
            if "data" in agent_output:
                data = agent_output["data"]
                if isinstance(data, str):
                    # Clean up any markdown that might have JSON wrapper artifacts
                    cleaned = data.strip()
                    # Remove common JSON wrapper patterns
                    if cleaned.startswith('{') and cleaned.endswith('}'):
                        # Try to extract markdown from malformed JSON
                        import re
                        # Look for markdown patterns
                        markdown_match = re.search(r'##\s+.+', cleaned, re.DOTALL)
                        if markdown_match:
                            return cleaned[markdown_match.start():].strip()
                    return cleaned
                elif isinstance(data, dict):
                    # Look for common text fields
                    for key in ["content", "text", "answer", "output", "markdown", "result"]:
                        if key in data and isinstance(data[key], str):
                            return data[key]
                    # If nothing found, convert to readable text
                    return json.dumps(data, indent=2)
            # Try other common fields
            for key in ["content", "text", "answer", "output", "markdown", "result"]:
                if key in agent_output and isinstance(agent_output[key], str):
                    return agent_output[key]

        # Fallback: convert to string and try to extract markdown
        text = str(agent_output)
        import re
        markdown_match = re.search(r'##\s+.+', text, re.DOTALL)
        if markdown_match:
            return text[markdown_match.start():].strip()
        return text

    def _serialize_message(self, msg: AgentMessage) -> Dict:
        """Serialize agent message for output."""
        return {
            "agent": msg.agent_name,
            "iteration": msg.iteration,
            "phase": msg.metadata.get("phase", "unknown"),
            "content": msg.content
        }

    def _generate_summary(self) -> Dict:
        """Generate summary of the collaborative workflow."""
        phases = {}
        for msg in self.conversation_history:
            phase = msg.metadata.get("phase", "unknown")
            if phase not in phases:
                phases[phase] = []
            phases[phase].append(msg.agent_name)

        return {
            "total_messages": len(self.conversation_history),
            "phases_completed": list(phases.keys()),
            "agent_participation": {
                "Researcher": sum(1 for m in self.conversation_history if m.agent_name == "Researcher"),
                "Critic": sum(1 for m in self.conversation_history if m.agent_name == "Critic"),
                "Editor": sum(1 for m in self.conversation_history if m.agent_name == "Editor")
            },
            "refinement_rounds": self.max_refinement_rounds
        }
