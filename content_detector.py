"""
Content Type Detection for Long-Form Generation

Automatically detects whether a query requires:
- Research (factual, analytical, comprehensive)
- Discussion (argumentative, philosophical, multi-perspective)
- Storytelling (narrative, creative, sequential)

And applies appropriate multi-turn strategies for each.
"""
import re
import logging
from typing import Tuple, Dict, List
from enum import Enum

logger = logging.getLogger(__name__)


class ContentType(Enum):
    """Types of long-form content."""
    RESEARCH = "research"
    DISCUSSION = "discussion"
    STORYTELLING = "storytelling"
    EXPLANATION = "explanation"
    ANALYSIS = "analysis"
    GENERAL = "general"


class ContentDetector:
    """Detects content type and estimates required depth."""

    def __init__(self):
        # Keywords and patterns for each content type
        self.patterns = {
            ContentType.RESEARCH: {
                'keywords': [
                    r'\b(research|study|analyze|examine|investigate|explore)\b',
                    r'\b(comprehensive|detailed|thorough|in-depth)\b',
                    r'\b(history of|overview of|background on)\b',
                    r'\b(what is|how does|why does|when did)\b',
                    r'\b(implications|applications|impact|effects)\b',
                    r'\b(explain|erxplain|expalin|expain)\b',  # Include common typos
                    r'\btell me (what|about|how|why|when)\b',  # "tell me what/about" = research
                ],
                'indicators': [
                    'explain quantum',
                    'erxplain quantum',
                    'explain ',
                    'erxplain ',
                    'describe the',
                    'what are the',
                    'provide an overview',
                    'research on',
                    'tell me what',
                    'tell me about',
                    'tell me how',
                    'tell me why',
                ]
            },
            ContentType.DISCUSSION: {
                'keywords': [
                    r'\b(discuss|debate|argue|compare|contrast)\b',
                    r'\b(perspective|viewpoint|opinion|stance)\b',
                    r'\b(pros and cons|advantages and disadvantages)\b',
                    r'\b(should we|is it|would it)\b',
                    r'\b(ethical|moral|philosophical)\b',
                ],
                'indicators': [
                    'discuss the',
                    'what do you think',
                    'debate whether',
                    'pros and cons',
                    'different perspectives',
                ]
            },
            ContentType.STORYTELLING: {
                'keywords': [
                    r'\b(story|tale|narrative|adventure|journey|sotry)\b',  # Include common typo
                    r'\b(character|protagonist|hero|villain)\b',
                    r'\b(write|create|imagine)\b',  # Removed "tell me" and "give me"
                    r'\b(once upon|chapter|scene|plot)\b',
                    r'\b(fiction|novel|short story)\b',
                    r'\b(kid friendly|for kids|children)\b',
                    r'\btell me a (story|tale)\b',  # Only "tell me a story/tale" = storytelling
                ],
                'indicators': [
                    'write a story',
                    'tell me a tale',
                    'tell me a story',
                    'create a narrative',
                    'fiction about',
                    'adventure of',
                    'story about',
                    'tale about',
                ]
            },
            ContentType.EXPLANATION: {
                'keywords': [
                    r'\b(explain|clarify|demonstrate|show how)\b',
                    r'\b(step by step|how to|guide|tutorial)\b',
                    r'\b(process|procedure|method|approach)\b',
                    r'\b(understand|learn|grasp)\b',
                ],
                'indicators': [
                    'explain how',
                    'step by step',
                    'how does',
                    'help me understand',
                ]
            },
            ContentType.ANALYSIS: {
                'keywords': [
                    r'\b(analyze|evaluate|assess|critique)\b',
                    r'\b(breakdown|dissect|examine)\b',
                    r'\b(strengths and weaknesses|pros cons)\b',
                    r'\b(in detail|thoroughly)\b',
                ],
                'indicators': [
                    'analyze the',
                    'critical analysis',
                    'in-depth look',
                    'detailed examination',
                ]
            }
        }

    def detect(self, query: str) -> Tuple[ContentType, int, Dict]:
        """
        Detect content type and estimate required response length.

        Args:
            query: User query

        Returns:
            Tuple of (ContentType, estimated_chunks, metadata)
        """
        query_lower = query.lower()

        # Calculate scores for each type
        scores = {}
        for content_type, patterns in self.patterns.items():
            score = 0

            # Check keywords
            for pattern in patterns['keywords']:
                if re.search(pattern, query_lower):
                    score += 2

            # Check indicators
            for indicator in patterns['indicators']:
                if indicator in query_lower:
                    score += 3

            scores[content_type] = score

        # Determine primary type
        if max(scores.values()) == 0:
            content_type = ContentType.GENERAL
            estimated_chunks = 1
        else:
            content_type = max(scores, key=scores.get)
            # Estimate chunks based on query complexity
            estimated_chunks = self._estimate_chunks(query, content_type)

        # Build metadata
        metadata = {
            'confidence': scores.get(content_type, 0) / 10.0,  # Normalize to 0-1
            'scores': {ct.value: s for ct, s in scores.items()},
            'query_length': len(query),
            'word_count': len(query.split()),
            'requires_multi_turn': estimated_chunks > 1
        }

        logger.info(
            f"📝 Content Detection: {content_type.value} "
            f"(confidence: {metadata['confidence']:.2f}, "
            f"chunks: {estimated_chunks})"
        )

        return content_type, estimated_chunks, metadata

    def _estimate_chunks(self, query: str, content_type: ContentType) -> int:
        """
        Estimate number of response chunks needed.

        Returns:
            Number of chunks (1-5)
        """
        word_count = len(query.split())

        # Base estimation by content type
        base_chunks = {
            ContentType.RESEARCH: 5,      # Multi-part research (increased for longer output)
            ContentType.DISCUSSION: 3,    # Multiple perspectives
            ContentType.STORYTELLING: 6,  # Multi-chapter story
            ContentType.EXPLANATION: 3,   # Step-by-step
            ContentType.ANALYSIS: 4,      # Detailed analysis
            ContentType.GENERAL: 1        # Single response
        }

        chunks = base_chunks.get(content_type, 1)

        # Adjust based on query complexity indicators
        complexity_keywords = [
            'comprehensive', 'detailed', 'thorough', 'in-depth',
            'extensive', 'complete', 'full', 'entire'
        ]

        query_lower = query.lower()
        for keyword in complexity_keywords:
            if keyword in query_lower:
                chunks += 1
                break

        # Cap at 5 chunks
        return min(chunks, 5)

    def get_continuation_prompt(
        self,
        content_type: ContentType,
        chunk_num: int,
        total_chunks: int,
        previous_content: str,
        original_query: str = None
    ) -> str:
        """
        Generate continuation prompt for multi-turn generation.

        Args:
            content_type: Type of content being generated
            chunk_num: Current chunk number (1-indexed)
            total_chunks: Total expected chunks
            previous_content: Previously generated content
            original_query: Original user request (to preserve requirements)

        Returns:
            Continuation prompt
        """
        if content_type == ContentType.RESEARCH:
            prev_summary = self._summarize(previous_content)
            return (
                f"Part {chunk_num}/{total_chunks}. Write 500-600 words of NEW technical content.\n\n"
                f"Previous content: {prev_summary}\n\n"
                f"Add NEW material (do not repeat):\n"
                f"- Additional mechanisms, processes, or equations\n"
                f"- Specific examples with numbers/data\n"
                f"- Experimental evidence or studies\n"
                f"- Applications with technical details\n"
                f"- Mathematical frameworks or theory\n\n"
                f"Be specific and technical. NO vague statements.\n\n"
                f"Output JSON with 'context' field as continuous text string."
            )

        elif content_type == ContentType.DISCUSSION:
            return (
                f"Continue the discussion (Part {chunk_num}/{total_chunks}). "
                f"Write at least 200-300 words of substantive content.\n\n"
                f"Present additional perspectives:\n"
                f"- Alternative viewpoints with detailed reasoning\n"
                f"- Counter-arguments with supporting evidence\n"
                f"- Nuanced considerations and complexities\n"
                f"- Synthesis and analysis of different ideas\n\n"
                f"IMPORTANT: Provide thorough, well-reasoned discussion. No superficial statements.\n\n"
                f"Previous discussion: {self._summarize(previous_content)}\n\n"
                f"Respond with JSON containing a 'context' field with your detailed discussion."
            )

        elif content_type == ContentType.STORYTELLING:
            # Preserve original requirements if provided
            requirements_reminder = ""
            if original_query:
                requirements_reminder = f"Original user request: {original_query}\n\n"

            story_so_far = self._summarize(previous_content)

            if chunk_num == 2:
                return (
                    f"{requirements_reminder}"
                    f"Continue the story (Chapter {chunk_num}/{total_chunks}).\n"
                    f"Develop the plot, introduce conflicts, deepen character development.\n"
                    f"Write at least 200-300 words of narrative.\n\n"
                    f"Story so far:\n{story_so_far}\n\n"
                    f"Respond with JSON containing a 'story' field with Chapter {chunk_num}."
                )
            elif chunk_num < total_chunks:
                return (
                    f"{requirements_reminder}"
                    f"Continue the story (Chapter {chunk_num}/{total_chunks}).\n"
                    f"Build tension, develop subplots, move toward climax.\n"
                    f"Write at least 200-300 words of narrative.\n\n"
                    f"Story so far:\n{story_so_far}\n\n"
                    f"Respond with JSON containing a 'story' field with Chapter {chunk_num}."
                )
            else:
                return (
                    f"{requirements_reminder}"
                    f"Conclude the story (Final Chapter {chunk_num}/{total_chunks}).\n"
                    f"Resolve conflicts, tie up loose ends, provide satisfying conclusion.\n"
                    f"Write at least 200-300 words of narrative.\n\n"
                    f"Story so far:\n{story_so_far}\n\n"
                    f"Respond with JSON containing a 'story' field with the conclusion."
                )

        elif content_type == ContentType.EXPLANATION:
            return (
                f"Continue the explanation (Part {chunk_num}/{total_chunks}). "
                f"Write at least 200-300 words of substantive content.\n\n"
                f"Elaborate on:\n"
                f"- Next steps in the process with detailed instructions\n"
                f"- Additional technical details and nuances\n"
                f"- Common pitfalls and comprehensive solutions\n"
                f"- Practical examples with specific use cases\n\n"
                f"IMPORTANT: Provide thorough, detailed explanations. No brief summaries.\n\n"
                f"Explained so far: {self._summarize(previous_content)}\n\n"
                f"Respond with JSON containing a 'context' field with your detailed explanation."
            )

        elif content_type == ContentType.ANALYSIS:
            return (
                f"Continue the analysis (Part {chunk_num}/{total_chunks}). "
                f"Write at least 200-300 words of substantive content.\n\n"
                f"Provide deeper insights:\n"
                f"- Additional dimensions and layers of analysis\n"
                f"- Supporting evidence with specific examples and data\n"
                f"- Critical evaluation with detailed reasoning\n"
                f"- Implications, significance, and conclusions\n\n"
                f"IMPORTANT: Provide in-depth analytical content. No shallow observations.\n\n"
                f"Analysis so far: {self._summarize(previous_content)}\n\n"
                f"Respond with JSON containing a 'context' field with your detailed analysis."
            )

        else:
            return (
                f"Continue from Part {chunk_num-1}. "
                f"Expand on the topic with additional details and insights.\n\n"
                f"Previous content: {self._summarize(previous_content)}"
            )

    def _summarize(self, text, max_words: int = 50) -> str:
        """Create a brief summary of text for context."""
        if text is None:
            return ""

        # Handle JSON/dict responses from agents
        if isinstance(text, dict):
            # Try common keys in priority order
            for key in ['summary', 'detailed_explanation', 'content', 'story', 'narrative']:
                if key in text and text[key]:
                    text = str(text[key])
                    break
            else:
                # No common key found - extract substantial text, skip metadata
                skip_keys = {'key_facts', 'context', 'topics', 'background', 'theoretical_framework',
                            'underlying_mechanisms', 'examples', 'practical_applications', 'metadata'}

                text_parts = []
                for key, value in text.items():
                    if key not in skip_keys and isinstance(value, str) and len(value) > 20:
                        text_parts.append(value)

                if text_parts:
                    text = " ".join(text_parts)
                else:
                    # Last resort: JSON dump
                    import json
                    text = json.dumps(text, indent=2)

        # Handle string
        if not isinstance(text, str):
            text = str(text)

        if not text:
            return ""

        words = text.split()
        if len(words) <= max_words:
            return text
        return ' '.join(words[:max_words]) + '...'


# Global instance
_detector = ContentDetector()


def detect_content_type(query: str) -> Tuple[ContentType, int, Dict]:
    """
    Detect content type for a query.

    Args:
        query: User query

    Returns:
        Tuple of (ContentType, estimated_chunks, metadata)
    """
    return _detector.detect(query)


def get_continuation_prompt(
    content_type: ContentType,
    chunk_num: int,
    total_chunks: int,
    previous_content: str,
    original_query: str = None
) -> str:
    """Generate continuation prompt."""
    return _detector.get_continuation_prompt(
        content_type, chunk_num, total_chunks, previous_content, original_query
    )
