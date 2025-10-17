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
        """Synthesize research sections into comprehensive technical output."""
        system_prompt = (
            "You are a technical editor. Merge multiple research sections into one cohesive, comprehensive article. "
            "Your synthesis must be 2000-2500 words minimum. "
            "PRESERVE ALL CONTENT - each section contains unique information. "
            "DO NOT remove content just because it seems repetitive - if two sections mention the same concept, COMBINE their information. "
            "Keep ALL: equations, data, mechanisms, examples, studies, applications, current research. "
            "Only remove identical phrasing (e.g., 'String theory is...'), but keep the substance. "
            "Create logical flow: fundamentals → mathematical formalism → experimental evidence → applications → future directions. "
            "CRITICAL: The detailed_explanation field MUST be plain continuous text - NOT a dict, NOT JSON, NOT sections with keys. "
            "Write comprehensive prose that integrates ALL information from ALL sections."
        )

        prompt = f"""Merge these research sections into a comprehensive article.

{input_data}

Output ONLY this exact JSON structure:
{{
  "summary": "3-4 sentence technical overview",
  "key_points": ["fact 1", "fact 2", "fact 3", ... 15-20 total],
  "detailed_explanation": "Write your 2000-2500 word comprehensive prose article here as a SINGLE CONTINUOUS TEXT STRING. Integrate ALL information from ALL sections - fundamentals, mathematical formalism, experimental evidence, applications, and future research. Do NOT use dict format, do NOT use section headers, do NOT use key-value pairs. Just write normal flowing prose. PRESERVE all technical depth, equations, examples, studies, applications, and research directions. Each section had unique content - include it ALL. Only remove identical phrasing, never substantive content.",
  "examples": ["example 1", "example 2", ... 10-15 total],
  "practical_applications": ["app 1", "app 2", ... 10-15 total]
}}

CRITICAL INSTRUCTIONS:
- detailed_explanation = plain prose string (2000-2500 words), NOT nested dict
- MUST include content from ALL input sections (fundamentals, math, experiments, applications, future)
- DO NOT condense or summarize - EXPAND and INTEGRATE
Output valid JSON now:"""

        return self.call_ollama(prompt, system_prompt)
