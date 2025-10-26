"""
AST (Agent Scoring & Threshold) Quality Assurance System
Validates output quality and triggers re-refinement if below threshold.
"""

import logging
from typing import Dict, List, Tuple
from dataclasses import dataclass
from agents.researcher import Researcher
from agents.critic import Critic
import json

logger = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Quality score from a single agent."""
    agent_name: str
    score: float  # 0.0 to 1.0
    reasoning: str
    issues: List[str]


class ASTQualityVoting:
    """
    Agent Scoring & Threshold system for quality validation.

    Uses multiple agents to vote on output quality:
    - Each agent scores the output (0.0 to 1.0)
    - Scores are aggregated
    - If below threshold, output is sent back for refinement
    """

    def __init__(self, model: str = "llama3.2", threshold: float = 0.7,
                 max_retries: int = 2, timeout: int = 300):
        """
        Initialize AST quality voting system.

        Args:
            model: Ollama model to use
            threshold: Minimum aggregate score to pass (0.0 to 1.0)
            max_retries: Maximum number of re-refinement attempts
            timeout: Inference timeout in seconds
        """
        self.model = model
        self.threshold = threshold
        self.max_retries = max_retries
        self.timeout = timeout

    def evaluate_quality(self, original_query: str, final_output: str,
                        ollama_url: str = "http://localhost:11434") -> Tuple[bool, float, List[QualityScore]]:
        """
        Evaluate output quality using multiple voting agents.

        Args:
            original_query: The original user query
            final_output: The final synthesized output to evaluate
            ollama_url: Ollama instance URL

        Returns:
            Tuple of (passed: bool, aggregate_score: float, individual_scores: List[QualityScore])
        """
        logger.info("🗳️  AST Quality Voting - Evaluating output quality")

        # Initialize voting agents
        quality_agents = [
            Researcher(self.model, timeout=self.timeout),
            Critic(self.model, timeout=self.timeout)
        ]

        # Define expected JSON schema for quality evaluation
        quality_schema = {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "reasoning": {"type": "string"},
                "issues": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["score", "reasoning", "issues"]
        }

        for agent in quality_agents:
            agent.ollama_url = ollama_url
            agent.expected_schema = quality_schema  # Enable TrustCall validation

        scores: List[QualityScore] = []

        # Each agent evaluates the quality
        for agent in quality_agents:
            score = self._get_agent_score(agent, original_query, final_output)
            scores.append(score)
            logger.info(f"  {agent.name}: {score.score:.2f}/1.0 - {score.reasoning}")

        # Aggregate scores (simple average)
        aggregate_score = sum(s.score for s in scores) / len(scores)
        passed = aggregate_score >= self.threshold

        if passed:
            logger.info(f"✅ Quality Check PASSED - Score: {aggregate_score:.2f}/{self.threshold:.2f}")
        else:
            logger.warning(f"❌ Quality Check FAILED - Score: {aggregate_score:.2f}/{self.threshold:.2f}")

        return passed, aggregate_score, scores

    def _get_agent_score(self, agent, original_query: str, final_output: str) -> QualityScore:
        """Get quality score from a single agent."""

        # Build evaluation prompt
        evaluation_prompt = f"""Evaluate the quality of this answer to the original query.

Original Query:
{original_query}

Final Answer:
{final_output}

Rate the answer on a scale of 0.0 to 1.0 based on:
1. Accuracy and correctness
2. Completeness - does it fully answer the query?
3. Clarity and readability (no repetition or rambling)
4. Structure and organization
5. Depth and detail (thorough but concise)
6. Formatting quality (proper LaTeX, no broken notation like "rac" or "\dotdot")

CRITICAL: Deduct points for:
- Repetitive content (same ideas restated multiple times)
- Excessive length or rambling
- Broken math formatting (missing backslashes, broken brackets)
- Wall of text without structure

Provide your evaluation in JSON format with:
- score (float 0.0 to 1.0)
- reasoning (string explaining the score)
- issues (list of specific problems found, empty list if none)

Example:
{{
  "score": 0.85,
  "reasoning": "Well-structured and accurate, but could provide more examples",
  "issues": ["Lacks concrete examples", "Could expand on practical applications"]
}}
"""

        system_prompt = (
            "You are a quality evaluation agent. Your role is to objectively assess "
            "the quality of answers based on accuracy, completeness, clarity, structure, and depth. "
            "Provide scores in JSON format with score (0.0-1.0), reasoning, and issues list."
        )

        try:
            result = agent.call_ollama(evaluation_prompt, system_prompt, force_json=True, use_trustcall=True)

            # Log the raw result for debugging
            logger.debug(f"Quality voting raw result from {agent.name}: {result}")

            # Extract score data - handle multiple possible formats
            data = None

            # Format 1: Direct dict with score/reasoning/issues
            if isinstance(result, dict) and 'score' in result:
                data = result
            # Format 2: Nested in 'data' key
            elif isinstance(result, dict) and 'data' in result:
                data = result['data']
                # If data is a JSON string, parse it
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse JSON string from {agent.name}: {data[:100]}")
                        data = None

            # Extract values from parsed data
            if isinstance(data, dict):
                score_val = data.get('score', 0.5)
                # Handle score as string
                if isinstance(score_val, str):
                    try:
                        score_val = float(score_val)
                    except ValueError:
                        score_val = 0.5

                reasoning = data.get('reasoning', 'No reasoning provided')
                issues = data.get('issues', [])
                if not isinstance(issues, list):
                    issues = []
            else:
                # Failed to extract data
                logger.warning(f"Could not extract quality data from {agent.name} - result type: {type(result)}")
                score_val = 0.5
                reasoning = "Invalid response format - could not parse quality evaluation"
                issues = ["Response parsing failed"]

            return QualityScore(
                agent_name=agent.name,
                score=max(0.0, min(1.0, score_val)),  # Clamp to 0-1
                reasoning=reasoning,
                issues=issues if isinstance(issues, list) else []
            )

        except Exception as e:
            logger.error(f"Error getting quality score from {agent.name}: {e}")
            return QualityScore(
                agent_name=agent.name,
                score=0.5,
                reasoning=f"Error during evaluation: {str(e)}",
                issues=["Evaluation error"]
            )

    def generate_improvement_feedback(self, original_query: str, final_output: str,
                                     quality_scores: List[QualityScore]) -> str:
        """
        Generate feedback for improvement based on quality scores.

        Args:
            original_query: Original user query
            final_output: Current final output
            quality_scores: List of quality scores from voting agents

        Returns:
            Feedback prompt for refinement
        """
        # Collect all issues
        all_issues = []
        for score in quality_scores:
            all_issues.extend(score.issues)

        # Remove duplicates while preserving order
        unique_issues = list(dict.fromkeys(all_issues))

        feedback = f"""QUALITY ASSURANCE FEEDBACK

Original Query: {original_query}

Current Answer Quality: BELOW THRESHOLD
- Aggregate Score: {sum(s.score for s in quality_scores) / len(quality_scores):.2f}/1.0
- Required Threshold: {self.threshold:.2f}/1.0

Agent Evaluations:
"""
        for score in quality_scores:
            feedback += f"\n{score.agent_name} ({score.score:.2f}/1.0): {score.reasoning}"

        if unique_issues:
            feedback += f"\n\nIdentified Issues:\n"
            for issue in unique_issues:
                feedback += f"- {issue}\n"

        feedback += f"""
Current Answer to Improve:
{final_output}

Your task:
1. Address ALL identified issues above
2. Improve accuracy, completeness, clarity, and depth
3. Maintain proper markdown formatting
4. Ensure the answer FULLY addresses: {original_query}

Provide an IMPROVED version of the answer that addresses these quality concerns.
"""

        return feedback
