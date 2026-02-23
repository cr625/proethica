"""
Utility functions for LLM interactions.
"""

import os
import re
import json
import logging
import importlib
import importlib.metadata
from typing import Any, Optional, Dict
from flask import current_app

logger = logging.getLogger(__name__)


def streaming_completion(client, model: str, max_tokens: int, prompt: str,
                         temperature: float = 0.1) -> str:
    """Call Anthropic API with streaming to prevent WSL2 TCP idle timeout.

    WSL2 kills TCP connections after ~60s of no data.  Non-streaming calls
    that take longer than 60s to process on the server side will fail.
    Streaming keeps data flowing throughout the request.

    Returns the full response text.
    """
    with client.messages.stream(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        response = stream.get_final_message()
    return response.content[0].text

def extract_json_from_response(response_text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from an LLM response.

    Handles common LLM response formats:
    - Raw JSON
    - JSON wrapped in markdown code blocks (```json ... ``` or ``` ... ```)
    - JSON with surrounding text

    Args:
        response_text: The raw text response from an LLM

    Returns:
        Parsed JSON as a dictionary

    Raises:
        ValueError: If no valid JSON can be extracted
    """
    if not response_text or not response_text.strip():
        raise ValueError("Empty response text")

    text = response_text.strip()

    # Try 1: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try 2: Strip markdown code fence (```json ... ``` or ``` ... ```)
    # Match ```json or ``` at start, ``` at end
    code_block_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', text)
    if code_block_match:
        try:
            return json.loads(code_block_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try 3: Find JSON object in text (for responses with surrounding text)
    # This regex finds the outermost { ... } block
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    # Try 4: Find JSON array in text
    array_match = re.search(r'\[[\s\S]*\]', text)
    if array_match:
        try:
            return json.loads(array_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract valid JSON from response: {text[:500]}")


class LLMUtilsConfig:
    """Configuration for LLM utilities"""
    USE_MOCK_RESPONSES = False

def _get_gemini_client_if_enabled() -> Optional[Any]:
    """Gemini client disabled - always returns None."""
    return None


def get_llm_client():
    """
    Get an LLM client based on configuration.
    
    Returns:
        An LLM client (Anthropic or OpenAI)
    """
    # First check for Anthropic
    try:
        import anthropic
        api_key = current_app.config.get('ANTHROPIC_API_KEY') or os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            # Determine Anthropic API version using multiple methods for reliability
            try:
                try:
                    anthropic_version = importlib.metadata.version("anthropic")
                except Exception:
                    anthropic_version = "unknown"
                        
                client = anthropic.Anthropic(api_key=api_key, timeout=180.0)
                
                # Add version info to client for easier compatibility checks
                # Current version structure:
                # <0.5.0 = very old API
                # 0.5x.x = newer messages API
                # >1.0 = likely future unified API
                if hasattr(client, 'chat') and hasattr(client.chat, 'completions'):
                    client.api_version = "v2"  # New unified API with chat.completions
                elif hasattr(client, 'messages') and hasattr(client.messages, 'create'):
                    client.api_version = "v1.5"  # Messages API (0.5x.x)
                elif hasattr(client, 'completion'):
                    client.api_version = "v1"  # Old API
                else:
                    client.api_version = "unknown"
                
                # Detect available models
                try:
                    if client.api_version == "v2" and hasattr(client, 'models'):
                        models = client.models.list()
                        available_models = [model.id for model in models.data]
                        client.available_models = available_models
                    else:
                        # Default models
                        from models import ModelConfig
                        client.available_models = [ModelConfig.CLAUDE_MODELS["sonnet-4.6"], ModelConfig.CLAUDE_MODELS["opus-4.6"], ModelConfig.CLAUDE_MODELS["haiku-4.5"]]
                except Exception:
                    # Fallback if models check fails
                    from models import ModelConfig
                    preferred_model = ModelConfig.get_default_model()
                    client.available_models = [preferred_model, ModelConfig.CLAUDE_MODELS["sonnet-4.6"], ModelConfig.CLAUDE_MODELS["opus-4.6"]]
                    
                model_list = ", ".join(client.available_models[:3]) + ("..." if len(client.available_models) > 3 else "")
                print(f"Initialized Anthropic client version {anthropic_version} ({client.api_version}) with models: {model_list}")
                return client
            except Exception as e:
                print(f"Error setting up Anthropic client: {str(e)}")
                raise
    except (ImportError, Exception) as e:
        print(f"Failed to initialize Anthropic: {str(e)}")
    
    # If Anthropic failed, try OpenAI
    try:
        import openai
        api_key = current_app.config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
        if api_key:
            client = openai.OpenAI(api_key=api_key)
            # Test with a simple request to make sure it's configured correctly
            models = client.models.list()
            return client
    except (ImportError, Exception) as e:
        print(f"Failed to initialize OpenAI: {str(e)}")
    
    # If both failed, raise an exception
    raise RuntimeError("No LLM client available. Please set up Anthropic or OpenAI API keys.")

def get_embedding_client():
    """
    Get an embedding client based on configuration.
    
    Returns:
        An embedding client
    """
    # First check for OpenAI (preferred for embeddings)
    try:
        import openai
        api_key = current_app.config.get('OPENAI_API_KEY') or os.getenv('OPENAI_API_KEY')
        if api_key:
            client = openai.OpenAI(api_key=api_key)
            # Test with a simple request to make sure it's configured correctly
            return client
    except (ImportError, Exception) as e:
        print(f"Failed to initialize OpenAI for embeddings: {str(e)}")
    
    # If OpenAI failed, try to use a local transformer-based embedding model
    try:
        import torch
        from sentence_transformers import SentenceTransformer
        
        # Load the model (will download if not available)
        model = SentenceTransformer('all-MiniLM-L6-v2')
        return model
    except (ImportError, Exception) as e:
        print(f"Failed to initialize local embedding model: {str(e)}")
    
    # If both failed, raise an exception
    raise RuntimeError("No embedding client available. Please set up OpenAI API keys or install sentence-transformers.")

def create_embeddings(texts, client=None):
    """
    Create embeddings for a list of texts.
    
    Args:
        texts: List of text strings to embed
        client: Optional client to use
        
    Returns:
        List of embeddings vectors
    """
    if not client:
        client = get_embedding_client()
    
    # Check if client is OpenAI
    if hasattr(client, 'embeddings'):
        try:
            # Use OpenAI embeddings
            response = client.embeddings.create(
                input=texts,
                model="text-embedding-ada-002"
            )
            return [item.embedding for item in response.data]
        except Exception as e:
            print(f"Error creating OpenAI embeddings: {str(e)}")
            raise
    
    # Assume it's a SentenceTransformer model
    try:
        embeddings = client.encode(texts)
        # Convert to Python lists for consistent return type
        return [embedding.tolist() for embedding in embeddings]
    except Exception as e:
        print(f"Error creating SentenceTransformer embeddings: {str(e)}")
        raise
