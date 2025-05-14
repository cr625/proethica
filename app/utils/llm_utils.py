"""
Utility functions for LLM interactions.
"""

import os
from typing import Any
import importlib
from flask import current_app

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
            # Determine Anthropic API version
            import pkg_resources
            anthropic_version = pkg_resources.get_distribution("anthropic").version
            client = anthropic.Anthropic(api_key=api_key)
            
            # Add version info to client for easier compatibility checks
            if anthropic_version.startswith('0.') or anthropic_version.startswith('1.'):
                client.api_version = "v1"
            else:
                client.api_version = "v2"
                
            # Detect available models
            try:
                if client.api_version == "v2" and hasattr(client, 'models'):
                    models = client.models.list()
                    available_models = [model.id for model in models.data]
                    client.available_models = available_models
                else:
                    # Default models for v1
                    client.available_models = ["claude-2.0", "claude-2.1", "claude-instant-1.2"]
            except Exception:
                # Fallback if models check fails
                preferred_model = os.getenv('CLAUDE_MODEL_VERSION', 'claude-3-7-sonnet-20250219')
                client.available_models = [preferred_model, "claude-3-7-sonnet-latest", "claude-3-haiku-20240307"]
                
            model_list = ", ".join(client.available_models[:3]) + ("..." if len(client.available_models) > 3 else "")
            print(f"Initialized Anthropic client version {anthropic_version} ({client.api_version}) with models: {model_list}")
            return client
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
