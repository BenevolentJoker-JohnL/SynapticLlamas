"""
Ollama GGUF Resolver - Extract GGUF files from Ollama's blob storage

Ollama stores models as GGUF files in ~/.ollama/models/blobs/ with SHA256 hash names.
This module resolves Ollama model names to their underlying GGUF blob paths,
enabling transparent use of Ollama models with llama.cpp distributed inference.

Architecture:
    ~/.ollama/models/
    ├── blobs/
    │   └── sha256-<hash>  ← Actual GGUF files
    └── manifests/
        └── registry.ollama.ai/library/<model>/<tag>  ← Model metadata

Example:
    resolver = OllamaGGUFResolver()
    gguf_path = resolver.resolve("llama3.1:405b")
    # Returns: /home/user/.ollama/models/blobs/sha256-abc123...
"""

import os
import json
import logging
import subprocess
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class OllamaGGUFResolver:
    """
    Resolves Ollama model names to GGUF file paths in Ollama's blob storage.

    This enables using Ollama models directly with llama.cpp without duplication.
    """

    def __init__(self, ollama_models_dir: Optional[str] = None):
        """
        Initialize resolver.

        Args:
            ollama_models_dir: Override Ollama models directory (default: ~/.ollama/models)
        """
        if ollama_models_dir:
            self.models_dir = Path(ollama_models_dir)
        else:
            self.models_dir = Path.home() / ".ollama" / "models"

        self.blobs_dir = self.models_dir / "blobs"
        self.manifests_dir = self.models_dir / "manifests"

        # Cache for resolved GGUF paths (model_name -> gguf_path)
        self._cache: Dict[str, str] = {}

        logger.info(f"OllamaGGUFResolver initialized: {self.models_dir}")

    def resolve(self, model_name: str) -> Optional[str]:
        """
        Resolve Ollama model name to GGUF blob path (with caching).

        Args:
            model_name: Ollama model name (e.g., "llama3.1:405b")

        Returns:
            Path to GGUF file, or None if not found

        Example:
            >>> resolver = OllamaGGUFResolver()
            >>> path = resolver.resolve("llama3.1:405b")
            >>> print(path)
            /home/user/.ollama/models/blobs/sha256-abc123...
        """
        # Check cache first
        if model_name in self._cache:
            logger.debug(f"✅ Cache hit for {model_name} → {self._cache[model_name]}")
            return self._cache[model_name]

        try:
            # Method 1: Use `ollama show` command (most reliable)
            gguf_path = self._resolve_via_ollama_show(model_name)
            if gguf_path:
                self._cache[model_name] = gguf_path
                return gguf_path

            # Method 2: Parse manifest files directly
            gguf_path = self._resolve_via_manifest(model_name)
            if gguf_path:
                self._cache[model_name] = gguf_path
                return gguf_path

            logger.warning(f"Could not resolve GGUF path for model: {model_name}")
            return None

        except Exception as e:
            logger.error(f"Error resolving GGUF for {model_name}: {e}")
            return None

    def _resolve_via_ollama_show(self, model_name: str) -> Optional[str]:
        """
        Resolve GGUF path using `ollama show` command.

        This queries Ollama's API to get the model manifest, which contains
        the SHA256 hash of the GGUF blob.
        """
        try:
            # Run `ollama show <model> --modelfile` to get model info
            result = subprocess.run(
                ["ollama", "show", model_name, "--modelfile"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                logger.debug(f"ollama show failed for {model_name}: {result.stderr}")
                return None

            # Parse output to find FROM line with blob reference
            # Format: FROM /path/to/blob OR FROM @sha256:<hash>
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line.startswith('FROM '):
                    from_path = line[5:].strip()

                    # Check if it's a blob reference
                    if from_path.startswith('@sha256:'):
                        # Extract hash and build blob path
                        blob_hash = from_path[1:]  # Remove @
                        blob_path = self.blobs_dir / f"sha256-{blob_hash.split(':')[1]}"

                        if blob_path.exists():
                            logger.info(f"✅ Resolved {model_name} → {blob_path}")
                            return str(blob_path)

                    elif from_path.startswith('/') and 'blobs' in from_path:
                        # Direct path reference
                        if Path(from_path).exists():
                            logger.info(f"✅ Resolved {model_name} → {from_path}")
                            return from_path

            return None

        except subprocess.TimeoutExpired:
            logger.warning(f"ollama show timed out for {model_name}")
            return None
        except FileNotFoundError:
            logger.warning("ollama command not found - is Ollama installed?")
            return None
        except Exception as e:
            logger.debug(f"Error in _resolve_via_ollama_show: {e}")
            return None

    def _resolve_via_manifest(self, model_name: str) -> Optional[str]:
        """
        Resolve GGUF path by parsing Ollama manifest files directly.

        Manifest structure:
            manifests/registry.ollama.ai/library/<model>/<tag>

        The manifest is a JSON file containing layer information,
        including the SHA256 digest of the GGUF blob.
        """
        try:
            # Parse model name into parts
            if ':' in model_name:
                model, tag = model_name.split(':', 1)
            else:
                model = model_name
                tag = 'latest'

            # Build manifest path
            # Format: manifests/registry.ollama.ai/library/<model>/<tag>
            manifest_path = (
                self.manifests_dir /
                "registry.ollama.ai" /
                "library" /
                model /
                tag
            )

            if not manifest_path.exists():
                logger.debug(f"Manifest not found: {manifest_path}")
                return None

            # Parse manifest JSON
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)

            # Find GGUF layer in manifest
            # The GGUF blob is typically in the layers array
            layers = manifest.get('layers', [])

            for layer in layers:
                media_type = layer.get('mediaType', '')
                digest = layer.get('digest', '')

                # GGUF layers have mediaType: application/vnd.ollama.image.model
                if 'model' in media_type.lower() and digest.startswith('sha256:'):
                    # Build blob path from digest
                    blob_hash = digest.replace(':', '-')
                    blob_path = self.blobs_dir / blob_hash

                    if blob_path.exists():
                        logger.info(f"✅ Resolved {model_name} → {blob_path}")
                        return str(blob_path)

            return None

        except Exception as e:
            logger.debug(f"Error in _resolve_via_manifest: {e}")
            return None

    def resolve_or_fallback(
        self,
        model_name: str,
        fallback_path: Optional[str] = None
    ) -> str:
        """
        Resolve GGUF path with fallback to explicit path.

        Args:
            model_name: Ollama model name
            fallback_path: Path to use if resolution fails

        Returns:
            Resolved GGUF path or fallback

        Raises:
            FileNotFoundError: If resolution fails and no fallback provided
        """
        # Try to resolve from Ollama storage
        gguf_path = self.resolve(model_name)

        if gguf_path:
            return gguf_path

        # Use fallback if provided
        if fallback_path:
            if Path(fallback_path).exists():
                logger.info(f"Using fallback GGUF path: {fallback_path}")
                return fallback_path
            else:
                raise FileNotFoundError(f"Fallback GGUF not found: {fallback_path}")

        # No fallback - raise error
        raise FileNotFoundError(
            f"Could not resolve GGUF for '{model_name}' and no fallback provided. "
            f"Please ensure the model is pulled in Ollama or provide explicit GGUF path."
        )

    def list_available_models(self) -> Dict[str, str]:
        """
        List all available GGUF models in Ollama storage.

        Returns:
            Dict mapping model names to GGUF blob paths
        """
        available = {}

        try:
            # Use `ollama list` to get all models
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                # Parse output (skip header)
                lines = result.stdout.strip().split('\n')[1:]

                for line in lines:
                    # Extract model name (first column)
                    parts = line.split()
                    if parts:
                        model_name = parts[0]
                        gguf_path = self.resolve(model_name)

                        if gguf_path:
                            available[model_name] = gguf_path

            return available

        except Exception as e:
            logger.error(f"Error listing models: {e}")
            return {}


# Convenience function for quick resolution
def resolve_ollama_model(model_name: str) -> Optional[str]:
    """
    Quick resolution of Ollama model to GGUF path.

    Args:
        model_name: Ollama model name

    Returns:
        Path to GGUF file or None

    Example:
        >>> gguf_path = resolve_ollama_model("llama3.1:405b")
        >>> print(gguf_path)
        /home/user/.ollama/models/blobs/sha256-abc123...
    """
    resolver = OllamaGGUFResolver()
    return resolver.resolve(model_name)
