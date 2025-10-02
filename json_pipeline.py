import json
import re
import logging

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


def standardize_to_json(agent_name, raw_output):
    """
    Convert agent output to standardized JSON format.

    Args:
        agent_name: Name of the agent
        raw_output: Raw text output from agent

    Returns:
        dict with standardized structure
    """
    # Try to extract existing JSON
    extracted_json = extract_json_from_text(raw_output)

    if extracted_json and isinstance(extracted_json, dict):
        # If valid JSON found, wrap it with agent metadata
        return {
            "agent": agent_name,
            "status": "success",
            "format": "json",
            "data": extracted_json
        }
    else:
        # If no JSON found, wrap the raw text
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
        dict with merged results
    """
    return {
        "pipeline": "SynapticLlamas",
        "agent_count": len(json_outputs),
        "agents": [output["agent"] for output in json_outputs],
        "outputs": json_outputs
    }
