from .base_agent import BaseAgent


class Critic(BaseAgent):
    def __init__(self, model="llama3.2", timeout=300):
        super().__init__("Critic", model, timeout=timeout)
        # Define expected JSON schema for TrustCall validation
        self.expected_schema = {
            "issues": list,
            "biases": list,
            "strengths": list,
            "recommendations": list
        }

    def process(self, input_data):
        """Analyze and critique the input, checking for accuracy and potential issues."""
        system_prompt = (
            "You are a critical analysis agent. Your role is to fact-check, "
            "identify potential issues, biases, or gaps in reasoning. "
            "Provide constructive criticism and highlight areas for improvement in JSON format with fields: "
            "issues (list), biases (list), strengths (list), recommendations (list)."
        )

        prompt = f"Critically analyze the following input:\n\n{input_data}\n\nProvide output as JSON."

        return self.call_ollama(prompt, system_prompt)
