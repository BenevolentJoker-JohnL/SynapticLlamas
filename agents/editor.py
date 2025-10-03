from .base_agent import BaseAgent


class Editor(BaseAgent):
    def __init__(self, model="llama3.2", timeout=300):
        super().__init__("Editor", model, timeout=timeout)
        # Define expected JSON schema for TrustCall validation
        self.expected_schema = {
            "summary": str,
            "key_points": list,
            "detailed_explanation": str,
            "examples": list,
            "practical_applications": list
        }

    def process(self, input_data):
        """Synthesize information into structured JSON output."""
        system_prompt = (
            "You are an expert editor. Synthesize information into a comprehensive, "
            "well-structured JSON output. Provide thorough explanations with concrete examples. "
            "Output valid JSON with fields: summary (string), key_points (list of strings), "
            "detailed_explanation (string with full explanation), examples (list of concrete examples), "
            "practical_applications (list of real-world uses)."
        )

        prompt = f"""Synthesize this information into comprehensive JSON:

{input_data}

Create a complete JSON structure with:
- summary: Brief 1-2 sentence overview
- key_points: List of 5-7 essential facts/concepts
- detailed_explanation: Full, thorough explanation covering all aspects, underlying mechanisms, and theory
- examples: List of 3-5 concrete, specific examples
- practical_applications: List of 3-5 real-world applications or use cases

Be comprehensive and detailed. Provide depth, not just surface-level information.
Output valid JSON now:"""

        return self.call_ollama(prompt, system_prompt)
