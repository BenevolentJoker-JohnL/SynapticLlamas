from .base_agent import BaseAgent


class Researcher(BaseAgent):
    def __init__(self, model="llama3.2", timeout=600):
        super().__init__("Researcher", model, timeout=timeout)
        # Define expected JSON schema for TrustCall validation
        self.expected_schema = {
            "key_facts": list,
            "context": str,
            "topics": list,
            "sources": list  # Added for RAG citations
        }

    def process(self, input_data):
        """Extract and gather comprehensive contextual information about the topic."""
        # Check if input contains RAG sources (from FlockParser)
        has_rag_sources = "[Source:" in input_data or "RELEVANT DOCUMENT EXCERPTS" in input_data

        if has_rag_sources:
            # Enhanced prompt for RAG with citations - AGGRESSIVE version
            system_prompt = (
                "You are an expert research agent. Your ONLY job is to write ONE detailed technical explanation in proper English.\n"
                "\n"
                "ABSOLUTE REQUIREMENTS:\n"
                "1. Write in COMPLETE SENTENCES with PROPER SPACING between all words\n"
                "2. Each sentence must have subject, verb, and proper punctuation\n"
                "3. Use proper English grammar - do NOT skip articles (a, an, the)\n"
                "4. Mathematical notation must be complete and readable (e.g., 'ρ† = ρ' not 'rho^dagger rho')\n"
                "5. Maintain logical flow - do NOT randomly jump between topics\n"
                "6. 500-600 words MINIMUM in the context field\n"
                "\n"
                "BAD EXAMPLE (DO NOT DO THIS):\n"
                "\"Quantum mechanics fundamental theory describes behavior matter energy smallest scales based two postulates\"\n"
                "\n"
                "GOOD EXAMPLE (DO THIS):\n"
                "\"Quantum mechanics is a fundamental theory that describes the behavior of matter and energy at the smallest scales. "
                "It is based on two key postulates: the principle of superposition and wave function collapse [1]. "
                "The superposition principle states that a quantum system can exist in multiple states simultaneously until measured. "
                "Wave function collapse occurs when a measurement forces the system into a definite state [2].\"\n"
                "\n"
                "CITATION RULES:\n"
                "- Use [1], [2], [3] to cite sources IMMEDIATELY after claims\n"
                "- Example: 'Einstein showed E=mc² [1]' NOT 'Einstein showed E=mc²'\n"
                "- Multiple sources: 'Quantum entanglement enables secure communication [1][2]'\n"
                "\n"
                "JSON FORMAT - Return ONLY this structure:\n"
                '{\n'
                '  "key_facts": ["Complete sentence fact 1.", "Complete sentence fact 2.", "Complete sentence fact 3."],\n'
                '  "context": "Your 500-600 word technical explanation written in proper English with complete sentences, proper spacing, logical flow, and inline citations [1][2]. Each sentence must be grammatically correct and flow naturally into the next. Do NOT skip words. Do NOT omit spaces. Do NOT write sentence fragments.",\n'
                '  "topics": ["Specific topic 1", "Specific topic 2", "Specific topic 3"],\n'
                '  "sources": ["document1.pdf", "document2.pdf"]\n'
                '}\n'
                "\n"
                "CRITICAL RULES:\n"
                "- context field = ONE STRING of complete, properly spaced sentences\n"
                "- EVERY factual claim MUST have a citation [1][2] - NO EXCEPTIONS\n"
                "- If you write a sentence without [1] or [2], it WILL BE REJECTED\n"
                "- NO missing spaces between words (write 'at the' NOT 'the')\n"
                "- NO sentence fragments (every sentence needs subject + verb)\n"
                "- NO random topic jumps (maintain logical progression)\n"
                "- NO broken math (write out equations properly)\n"
                "- YES proper grammar, YES complete thoughts, YES logical flow, YES citations on every claim"
            )
        else:
            # Standard prompt without citations - AGGRESSIVE version
            system_prompt = (
                "You are an expert research agent. Your ONLY job is to write ONE detailed technical explanation in proper English.\n"
                "\n"
                "ABSOLUTE REQUIREMENTS:\n"
                "1. Write in COMPLETE SENTENCES with PROPER SPACING between all words\n"
                "2. Each sentence must have subject, verb, and proper punctuation\n"
                "3. Use proper English grammar - do NOT skip articles (a, an, the)\n"
                "4. Mathematical notation must be complete and readable (e.g., 'E = mc²' not 'E mc')\n"
                "5. Maintain logical flow - do NOT randomly jump between topics\n"
                "6. 500-600 words MINIMUM in the context field\n"
                "\n"
                "BAD EXAMPLE (DO NOT DO THIS):\n"
                "\"Quantum mechanics fundamental theory describes behavior matter energy smallest scales based two postulates\"\n"
                "\n"
                "GOOD EXAMPLE (DO THIS):\n"
                "\"Quantum mechanics is a fundamental theory that describes the behavior of matter and energy at the smallest scales. "
                "It is based on two key postulates: the principle of superposition and wave function collapse. "
                "The superposition principle states that a quantum system can exist in multiple states simultaneously until measured. "
                "Wave function collapse occurs when a measurement forces the system into a definite state.\"\n"
                "\n"
                "JSON FORMAT - Return ONLY this structure:\n"
                '{\n'
                '  "key_facts": ["Complete sentence fact 1.", "Complete sentence fact 2.", "Complete sentence fact 3."],\n'
                '  "context": "Your 500-600 word technical explanation written in proper English with complete sentences, proper spacing, and logical flow. Each sentence must be grammatically correct and flow naturally into the next. Do NOT skip words. Do NOT omit spaces. Do NOT write sentence fragments.",\n'
                '  "topics": ["Specific topic 1", "Specific topic 2", "Specific topic 3"],\n'
                '  "sources": []\n'
                '}\n'
                "\n"
                "CRITICAL RULES:\n"
                "- context field = ONE STRING of complete, properly spaced sentences\n"
                "- NO missing spaces between words (write 'at the' NOT 'the')\n"
                "- NO sentence fragments (every sentence needs subject + verb)\n"
                "- NO random topic jumps (maintain logical progression)\n"
                "- NO broken math (write out equations properly)\n"
                "- YES proper grammar, YES complete thoughts, YES logical flow"
            )

        prompt = f"{input_data}\n\nProvide comprehensive technical research as JSON. The context field must be a plain text string."

        return self.call_ollama(prompt, system_prompt)
