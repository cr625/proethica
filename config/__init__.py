"""
Configuration package for the AI Ethical DM application.
"""

import os
import sys
import importlib
from flask import Config
from config.environment import config as base_config

def get_app_config():
    """
    Get Flask-compatible configuration based on the current environment.
    
    Returns:
        dict: Configuration dictionary for the current environment
    """
    environment = os.environ.get('ENVIRONMENT', 'development')
    print(f"Loading configuration for environment: {environment}")
    
    # Create a dictionary to hold all configuration values
    config_dict = {}
    
    # Copy base config values
    for key, value in vars(base_config).items():
        if not key.startswith('__'):
            config_dict[key] = value
    
    # Try to import environment-specific config
    try:
        env_module_path = f"config.environments.{environment}"
        env_module = importlib.import_module(env_module_path)
        
        # Update with environment-specific values
        for key, value in vars(env_module.config).items():
            if not key.startswith('__'):
                config_dict[key] = value
                
        print(f"Successfully loaded configuration for '{environment}' environment")
    except (ImportError, AttributeError) as e:
        print(f"Warning: Error loading specific configuration for environment '{environment}': {e}")
        print("Using base configuration")
    
    # Make sure critical values are set
    if 'SQLALCHEMY_DATABASE_URI' not in config_dict:
        # Set a default if missing
        db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
        config_dict['SQLALCHEMY_DATABASE_URI'] = db_url
        print(f"Using database URL from environment: {db_url}")

    return config_dict

app_config = get_app_config()
