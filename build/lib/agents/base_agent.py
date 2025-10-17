from abc import ABC, abstractmethod
import requests
import json
import time
import sys
import os
import logging
import asyncio

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from json_pipeline import standardize_to_json
from trustcall import trust_validator

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    def __init__(self, name, model="llama3.2", ollama_url=None, timeout=300, priority=5):
        self.name = name
        self.model = model

        # Use SOLLOL by default if no URL specified
        if ollama_url is None:
            from sollol_adapter import get_adapter
            adapter = get_adapter()
            ollama_url = adapter.get_ollama_url()
            self.priority = adapter.get_priority_for_agent(name)
        else:
            self.priority = priority

        self.ollama_url = ollama_url
        self.execution_time = 0
        self.timeout = timeout  # Default 5 minutes for CPU inference
        self.expected_schema = {}  # Subclasses can define expected JSON schema

    def call_ollama(self, prompt, system_prompt=None, force_json=True, use_trustcall=True):
        """Call Ollama API with the given prompt using SOLLOL intelligent routing."""
        start_time = time.time()

        # Debug: Check what routing is available
        has_hybrid = hasattr(self, '_hybrid_router_sync') and self._hybrid_router_sync is not None
        has_lb = hasattr(self, '_load_balancer') and self._load_balancer is not None
        logger.info(f"🔍 {self.name}: has_hybrid={has_hybrid}, has_lb={has_lb}, model={self.model}")

        # Check if HybridRouter sync wrapper is available for RPC sharding
        if hasattr(self, '_hybrid_router_sync') and self._hybrid_router_sync is not None:
            try:
                logger.info(f"🔀 Using HybridRouter for {self.model}")

                # Convert to messages format
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})

                # Call sync wrapper (runs in background thread, no event loop issues)
                response = self._hybrid_router_sync.route_request(
                    model=self.model,
                    messages=messages,
                    stream=False,
                    timeout=self.timeout
                )

                self.execution_time = time.time() - start_time
                logger.info(f"✅ {self.name} completed via HybridRouter in {self.execution_time:.2f}s")

                # Extract content from response
                if isinstance(response, dict):
                    if 'message' in response:
                        raw_output = response['message'].get('content', '')
                    elif 'response' in response:
                        raw_output = response['response']
                    elif 'content' in response:
                        raw_output = response['content']
                    else:
                        raw_output = str(response)
                else:
                    raw_output = str(response)

                # Use TrustCall validation if enabled and schema defined
                if use_trustcall and force_json and hasattr(self, 'expected_schema') and self.expected_schema:
                    # Create repair function that can call LLM again via HybridRouter
                    def repair_fn(repair_prompt):
                        try:
                            repair_messages = [{"role": "user", "content": repair_prompt}]
                            repair_response = self._hybrid_router_sync.route_request(
                                model=self.model,
                                messages=repair_messages,
                                stream=False,
                                timeout=self.timeout
                            )
                            if isinstance(repair_response, dict):
                                if 'message' in repair_response:
                                    return repair_response['message'].get('content', '{}')
                                elif 'response' in repair_response:
                                    return repair_response['response']
                                elif 'content' in repair_response:
                                    return repair_response['content']
                            return "{}"
                        except Exception as e:
                            logger.error(f"HybridRouter repair call failed: {e}")
                            return "{}"

                    # Validate and repair using TrustCall
                    validated_json = trust_validator.validate_and_repair(
                        raw_output,
                        self.expected_schema,
                        repair_fn,
                        self.name
                    )

                    return {
                        "agent": self.name,
                        "status": "success",
                        "format": "json",
                        "data": validated_json
                    }
                else:
                    # Fallback to old standardization
                    return {
                        "agent": self.name,
                        "status": "success",
                        "format": "json" if force_json else "text",
                        "data": standardize_to_json(self.name, raw_output) if force_json else raw_output
                    }
            except Exception as e:
                logger.error(f"❌ HybridRouter failed for {self.name}: {e}")
                import traceback
                logger.error(traceback.format_exc())
                # Fall through to regular Ollama call

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

        # Get SOLLOL routing decision if using load balancer
        routing_decision = None
        routing_metadata = {}

        # Check if we're in distributed mode with SOLLOL
        if hasattr(self, '_load_balancer') and self._load_balancer is not None:
            try:
                routing_decision = self._load_balancer.route_request(
                    payload=payload,
                    agent_name=self.name,
                    priority=self.priority
                )
                # Use the node URL from routing decision
                url = f"{routing_decision.node.url}/api/generate"
                routing_metadata = self._load_balancer.get_routing_metadata(routing_decision)

                routing_msg = (
                    f"🎯 SOLLOL routed {self.name} to {routing_decision.node.url} "
                    f"(score: {routing_decision.decision_score:.1f})"
                )
                logger.info(routing_msg)
                # Also print to stdout for CLI visibility
                print(f"   {routing_msg}")
            except Exception as e:
                logger.error(f"❌ SOLLOL routing failed, using default URL: {e}")
                url = f"{self.ollama_url}/api/generate"
        else:
            url = f"{self.ollama_url}/api/generate"
            logger.info(f"📍 {self.name} using default URL: {self.ollama_url}")

        try:
            logger.info(f"📤 {self.name} sending request to {url} (timeout: {self.timeout}s)")
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            self.execution_time = time.time() - start_time
            completion_msg = f"✅ {self.name} completed in {self.execution_time:.2f}s"
            logger.info(completion_msg)
            # Also print to stdout for CLI visibility
            print(f"   {completion_msg}")
            raw_output = result.get("response", "")

            # Record performance for SOLLOL adaptive learning
            if routing_decision and hasattr(self, '_load_balancer'):
                actual_duration_ms = self.execution_time * 1000
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=actual_duration_ms,
                    success=True,
                    error=None
                )

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

                # Add SOLLOL routing metadata
                if routing_metadata:
                    validated_json.update(routing_metadata)

                return validated_json
            else:
                # Fallback to old standardization
                standardized = standardize_to_json(self.name, raw_output)

                # Add SOLLOL routing metadata
                if routing_metadata:
                    standardized.update(routing_metadata)

                return standardized

        except requests.exceptions.Timeout as e:
            elapsed = time.time() - start_time
            logger.error(f"⏱️ TIMEOUT: {self.name} request to {url} timed out after {elapsed:.2f}s (limit: {self.timeout}s)")

            # Record failure for SOLLOL
            if routing_decision and hasattr(self, '_load_balancer'):
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=elapsed * 1000,
                    success=False,
                    error=f"Timeout after {elapsed:.2f}s"
                )

            self.execution_time = elapsed
            return {
                "agent": self.name,
                "status": "error",
                "format": "text",
                "data": {"error": f"Request timed out after {elapsed:.2f}s"}
            }

        except requests.exceptions.ConnectionError as e:
            elapsed = time.time() - start_time
            logger.error(f"🔌 CONNECTION ERROR: {self.name} could not connect to {url}: {e}")

            # Record failure for SOLLOL
            if routing_decision and hasattr(self, '_load_balancer'):
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=elapsed * 1000,
                    success=False,
                    error=f"Connection error: {str(e)}"
                )

            self.execution_time = elapsed
            return {
                "agent": self.name,
                "status": "error",
                "format": "text",
                "data": {"error": f"Connection error: {str(e)}"}
            }

        except requests.exceptions.HTTPError as e:
            # Record failure for SOLLOL
            if routing_decision and hasattr(self, '_load_balancer'):
                actual_duration_ms = (time.time() - start_time) * 1000
                self._load_balancer.record_performance(
                    decision=routing_decision,
                    actual_duration_ms=actual_duration_ms,
                    success=False,
                    error=str(e)
                )

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
                    standardized = standardize_to_json(self.name, raw_output)

                    # Add routing metadata
                    if routing_metadata:
                        standardized.update(routing_metadata)

                    return standardized
                except Exception as retry_error:
                    self.execution_time = time.time() - start_time
                    error_response = {
                        "agent": self.name,
                        "status": "error",
                        "format": "text",
                        "data": {"error": str(retry_error)}
                    }

                    # Add routing metadata even on error
                    if routing_metadata:
                        error_response.update(routing_metadata)

                    return error_response
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
