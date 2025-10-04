from .base_agent import BaseAgent


class Researcher(BaseAgent):
    def __init__(self, model="llama3.2", timeout=300):
        super().__init__("Researcher", model, timeout=timeout)
        # Define expected JSON schema for TrustCall validation
        self.expected_schema = {
            "key_facts": list,
            "context": str,
            "topics": list
        }

    def process(self, input_data):
        """Extract and gather comprehensive contextual information about the topic."""
        system_prompt = (
            "You are an expert research agent specializing in comprehensive, in-depth technical analysis. "
            "Write detailed technical explanations (500-600 words minimum) with: "
            "specific equations, mechanisms, experimental data, concrete examples, and technical evidence. "
            "Include numbers, formulas, specific studies, and technical details. NO vague generalities. "
            "Respond ONLY with valid JSON in this exact format:\n"
            '{\n'
            '  "key_facts": ["fact 1", "fact 2", "fact 3", ...],\n'
            '  "context": "Your detailed technical explanation goes here as a single string...",\n'
            '  "topics": ["topic 1", "topic 2", "topic 3", ...]\n'
            '}\n\n'
            "CRITICAL: The 'context' field MUST be a single continuous STRING (not a dict, not sections). "
            "Write 500-600 words of technical prose covering fundamentals, mechanisms, math, evidence, and applications."
        )

        prompt = f"{input_data}\n\nProvide comprehensive technical research as JSON. The context field must be a plain text string."

        return self.call_ollama(prompt, system_prompt)
