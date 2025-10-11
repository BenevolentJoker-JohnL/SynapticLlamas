import json
import re
import logging
from trustcall import trust_validator

logger = logging.getLogger(__name__)


def fix_malformed_json(json_str):
    """
    Attempt to fix common JSON formatting issues.
    """
    # Remove trailing commas before closing braces/brackets
    json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)

    # Fix single quotes to double quotes
    json_str = json_str.replace("'", '"')

    # Fix unquoted keys (common LLM mistake)
    json_str = re.sub(r'(\w+):', r'"\1":', json_str)

    # Remove duplicate quotes
    json_str = re.sub(r'"{2,}', '"', json_str)

    return json_str


def extract_json_from_text(text):
    """
    Extract JSON from text that may contain markdown, code blocks, or plain text.
    Handles various formats:
    - ```json {...} ```
    - ```{...}```
    - Plain JSON text
    - Mixed text with JSON embedded
    - Malformed JSON with common errors
    """
    # Remove any leading/trailing whitespace
    text = text.strip()

    # Try to find JSON in code blocks first
    json_block_patterns = [
        r'```json\s*(\{.*?\})\s*```',  # ```json {...} ```
        r'```json\s*(\[.*?\])\s*```',  # ```json [...] ```
        r'```\s*(\{.*?\})\s*```',       # ```{...}```
        r'```\s*(\[.*?\])\s*```',       # ```[...]```
        r'(\{[^{}]*\{[^{}]*\}[^{}]*\})',  # Nested JSON objects
        r'(\[[^\[\]]*\[[^\[\]]*\][^\[\]]*\])',  # Nested JSON arrays
        r'(\{[^{}]+\})',                  # Simple JSON object
        r'(\[[^\[\]]+\])',                # Simple JSON array
    ]

    for pattern in json_block_patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                # Try to fix and parse
                try:
                    fixed_json = fix_malformed_json(json_str)
                    return json.loads(fixed_json)
                except:
                    continue

    # If no valid JSON found in code blocks, try the entire text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to fix the entire text
        try:
            fixed_text = fix_malformed_json(text)
            return json.loads(fixed_text)
        except:
            pass

    # Last resort: try to extract anything that looks like JSON
    json_like = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
    if json_like:
        json_str = json_like.group(0)
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                fixed_json = fix_malformed_json(json_str)
                return json.loads(fixed_json)
            except:
                pass

    return None


def standardize_to_json(agent_name, raw_output, expected_schema=None, repair_fn=None):
    """
    Convert agent output to standardized JSON format with TrustCall validation.

    Args:
        agent_name: Name of the agent
        raw_output: Raw text output from agent
        expected_schema: Optional expected schema for validation
        repair_fn: Optional function to call LLM for repair

    Returns:
        dict with standardized structure
    """
    # Try to extract existing JSON
    extracted_json = extract_json_from_text(raw_output)

    if extracted_json and isinstance(extracted_json, dict):
        # If valid JSON found, validate with TrustCall if schema provided
        if expected_schema and repair_fn:
            logger.info(f"🔍 {agent_name} - Validating JSON with TrustCall")
            validated_json = trust_validator.validate_and_repair(
                json.dumps(extracted_json),
                expected_schema,
                repair_fn,
                agent_name
            )
            return {
                "agent": agent_name,
                "status": "success",
                "format": "json",
                "data": validated_json
            }
        else:
            # No schema validation, just wrap it
            return {
                "agent": agent_name,
                "status": "success",
                "format": "json",
                "data": extracted_json
            }
    else:
        # If no JSON found, try TrustCall repair if available
        if expected_schema and repair_fn:
            logger.warning(f"⚠️  {agent_name} did not output valid JSON. Attempting TrustCall repair...")
            repaired_json = trust_validator.validate_and_repair(
                raw_output,
                expected_schema,
                repair_fn,
                agent_name
            )

            # Check if repair was successful
            if repaired_json and not repaired_json.get("error"):
                return {
                    "agent": agent_name,
                    "status": "success",
                    "format": "json",
                    "data": repaired_json
                }

        # Fallback: wrap the raw text
        logger.warning(f"{agent_name} did not output valid JSON. Wrapping raw text.")
        return {
            "agent": agent_name,
            "status": "success",
            "format": "text",
            "data": {
                "content": raw_output.strip()
            }
        }


def validate_json_output(json_output):
    """
    Validate that the JSON output has the required structure.

    Required fields:
    - agent: str
    - status: str
    - format: str
    - data: dict
    """
    required_fields = ["agent", "status", "format", "data"]

    if not isinstance(json_output, dict):
        return False

    for field in required_fields:
        if field not in json_output:
            return False

    if not isinstance(json_output["data"], dict):
        return False

    return True


def merge_json_outputs(json_outputs):
    """
    Merge multiple JSON outputs into a single structured result.

    Args:
        json_outputs: List of standardized JSON outputs

    Returns:
        dict with merged results including synthesized final_output
    """
    # Synthesize final_output from agent outputs
    final_sections = []

    for output in json_outputs:
        agent_name = output.get("agent", "Unknown")
        data = output.get("data", {})

        # Handle case where data.content is a JSON string that needs parsing
        if "content" in data and isinstance(data["content"], str):
            try:
                # Try to parse content as JSON
                parsed_content = extract_json_from_text(data["content"])
                if parsed_content and isinstance(parsed_content, dict):
                    data = parsed_content
            except:
                pass

        # Extract meaningful content from each agent
        if output.get("format") == "json" or isinstance(data, dict):
            # Try to get context or content field
            content = data.get("context", data.get("content", ""))
            key_facts = data.get("key_facts", [])
            topics = data.get("topics", [])

            section = f"## {agent_name} Analysis\n\n"

            if content and isinstance(content, str):
                section += f"{content}\n\n"

            if key_facts and isinstance(key_facts, list):
                section += "**Key Points:**\n"
                for fact in key_facts:
                    section += f"- {fact}\n"
                section += "\n"

            if topics and isinstance(topics, list):
                section += "**Topics Covered:** " + ", ".join(str(t) for t in topics) + "\n\n"

        else:
            # Text format
            content = data.get("content", str(data)) if isinstance(data, dict) else str(data)
            section = f"## {agent_name} Analysis\n\n{content}\n\n"

        if section.strip() and section != f"## {agent_name} Analysis\n\n\n\n":
            final_sections.append(section)

    # Create comprehensive final output
    final_output = "\n".join(final_sections) if final_sections else "No output generated"

    return {
        "pipeline": "SynapticLlamas",
        "agent_count": len(json_outputs),
        "agents": [output["agent"] for output in json_outputs],
        "outputs": json_outputs,
        "final_output": final_output
    }
