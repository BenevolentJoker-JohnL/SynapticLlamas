from .base_agent import BaseAgent


class Storyteller(BaseAgent):
    def __init__(self, model="llama3.2", timeout=300):
        super().__init__("Storyteller", model, timeout=timeout)
        # Minimal schema - just story content, no analytical metadata
        self.expected_schema = {
            "story": str
        }

    def process(self, input_data):
        """Generate creative narrative story content."""
        system_prompt = (
            "You are a creative storyteller and narrative writer. "
            "Your role is to write engaging, imaginative stories with vivid descriptions, "
            "compelling characters, and flowing narrative. "
            "Focus on creative prose, not analysis or meta-commentary. "
            "Write actual story content, not descriptions ABOUT stories. "
            "Respond with JSON containing a 'story' field with your narrative text."
        )

        prompt = f"{input_data}\n\nWrite creative narrative content as requested. Respond with JSON."

        return self.call_ollama(prompt, system_prompt)
