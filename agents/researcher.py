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
        """Extract and gather contextual information about the topic."""
        system_prompt = (
            "You are a research agent. Your role is to extract key facts, "
            "gather relevant context, and identify important topics from the input. "
            "Provide comprehensive background information in JSON format with fields: "
            "key_facts (list), context (string), topics (list)."
        )

        prompt = f"Research and extract key information from the following:\n\n{input_data}\n\nProvide output as JSON."

        return self.call_ollama(prompt, system_prompt)
