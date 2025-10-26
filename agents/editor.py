from .base_agent import BaseAgent


class Editor(BaseAgent):
    def __init__(self, model="llama3.2", timeout=1200):
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
        """Synthesize research sections into comprehensive technical output."""
        system_prompt = (
            "You are a technical editor. Synthesize research into a clear, well-structured answer. "
            "Be thorough but concise - quality over quantity. "
            "Eliminate redundancy while preserving key information. "
            "Use proper formatting for equations and math notation. "
            "Avoid repetition - if a concept is mentioned, explain it once clearly rather than restating. "
            "Target 500-800 words for detailed_explanation - enough for depth without rambling."
        )

        prompt = f"""Synthesize this research into a clear, comprehensive answer.

{input_data}

Output ONLY this exact JSON structure:
{{
  "summary": "2-3 sentence overview answering the core question",
  "key_points": ["fact 1", "fact 2", "fact 3", ... 5-8 key points],
  "detailed_explanation": "Write a clear, well-organized 500-800 word explanation here. Structure it logically with distinct sections. Use proper LaTeX/math formatting. Be thorough but avoid repetition. Each concept should be explained once, clearly. Focus on: core principles, how it works, important details, and significance.",
  "examples": ["example 1", "example 2", ... 3-5 concrete examples],
  "practical_applications": ["app 1", "app 2", ... 3-5 real applications]
}}

QUALITY GUIDELINES:
- Concise but thorough (500-800 words for detailed_explanation)
- No repetition - explain each concept once
- Proper formatting for math/equations (use LaTeX: \\frac, \\sqrt, |ψ⟩, etc.)
- Clear logical structure
- Focus on accuracy and clarity
Output valid JSON now:"""

        return self.call_ollama(prompt, system_prompt)
