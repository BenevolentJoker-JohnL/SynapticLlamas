from abc import ABC, abstractmethod
import requests
import json
import time
import sys
import os
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_pipeline import standardize_to_json
from trustcall import trust_validator

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, name, model="llama3.2", ollama_url="http://localhost:11434", timeout=300):
        self.name = name
        self.model = model
        self.ollama_url = ollama_url
        self.execution_time = 0
        self.timeout = timeout  # Default 5 minutes for CPU inference
        self.expected_schema = {}  # Subclasses can define expected JSON schema

    def call_ollama(self, prompt, system_prompt=None, force_json=True, use_trustcall=True):
        """Call Ollama API with the given prompt."""
        start_time = time.time()

        url = f"{self.ollama_url}/api/generate"

        # Build payload - try with format: json first
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        if force_json:
            payload["format"] = "json"

        if system_prompt:
            payload["system"] = system_prompt

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            self.execution_time = time.time() - start_time
            raw_output = result.get("response", "")

            # Use TrustCall validation and repair if enabled and schema defined
            if use_trustcall and force_json and self.expected_schema:
                # Create repair function that can call LLM again
                def repair_fn(repair_prompt):
                    repair_payload = {
                        "model": self.model,
                        "prompt": repair_prompt,
                        "stream": False
                    }
                    try:
                        repair_response = requests.post(url, json=repair_payload, timeout=self.timeout)
                        repair_response.raise_for_status()
                        repair_result = repair_response.json()
                        return repair_result.get("response", "")
                    except Exception as e:
                        logger.error(f"Repair call failed: {e}")
                        return "{}"

                # Validate and repair using TrustCall
                validated_json = trust_validator.validate_and_repair(
                    raw_output,
                    self.expected_schema,
                    repair_fn,
                    self.name
                )
                return validated_json
            else:
                # Fallback to old standardization
                return standardize_to_json(self.name, raw_output)

        except requests.exceptions.HTTPError as e:
            # If format: json not supported, retry without it
            if force_json and "format" in payload:
                logger.warning(f"{self.name}: Model may not support format parameter, retrying without it")
                payload.pop("format", None)
                try:
                    response = requests.post(url, json=payload, timeout=self.timeout)
                    response.raise_for_status()
                    result = response.json()
                    self.execution_time = time.time() - start_time
                    raw_output = result.get("response", "")
                    return standardize_to_json(self.name, raw_output)
                except Exception as retry_error:
                    self.execution_time = time.time() - start_time
                    return {
                        "agent": self.name,
                        "status": "error",
                        "format": "text",
                        "data": {"error": str(retry_error)}
                    }
            else:
                self.execution_time = time.time() - start_time
                return {
                    "agent": self.name,
                    "status": "error",
                    "format": "text",
                    "data": {"error": str(e)}
                }
        except Exception as e:
            self.execution_time = time.time() - start_time
            return {
                "agent": self.name,
                "status": "error",
                "format": "text",
                "data": {"error": str(e)}
            }

    @abstractmethod
    def process(self, input_data):
        """Process input data and return standardized JSON output."""
        pass

    def get_metrics(self):
        """Return performance metrics."""
        return {
            "agent": self.name,
            "execution_time": round(self.execution_time, 2),
            "model": self.model
        }
