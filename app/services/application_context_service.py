#!/usr/bin/env python
"""
ApplicationContextService: Service for aggregating application context for LLMs.

This service provides structured context about the application state,
including database entities, available navigation, and relevant
information to enhance LLM capabilities.
"""

import os
import json
import importlib
import inspect
import re
from typing import Dict, List, Any, Optional, Union, Type
from datetime import datetime
import time

from app import db
from app.models.world import World
from app.models.scenario import Scenario
from app.models.character import Character
from app.models.event import Event, Action
from app.models.resource import Resource
from app.models.entity_triple import EntityTriple

from app.services.entity_triple_service import EntityTripleService
from app.services.temporal_context_service import TemporalContextService
from app.services.mcp_client import MCPClient
from app.services.context_providers.base_provider import ContextProvider
from app.services.context_providers.default_provider import DefaultContextProvider


class ApplicationContextService:
    """
    Service for aggregating and providing application context to LLMs.
    This service collects information about the database state, available entities,
    and application navigation to enhance the LLM's understanding of the system.
    """
    
    # Current version of the context schema
    CONTEXT_VERSION = "1.0.0"
    
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'ApplicationContextService':
        """Get singleton instance of ApplicationContextService."""
        if cls._instance is None:
            cls._instance = ApplicationContextService()
        return cls._instance
    
    def __init__(self):
        """Initialize service with connections to other services."""
        self.entity_triple_service = EntityTripleService()
        self.temporal_context_service = TemporalContextService()
        self.mcp_client = MCPClient.get_instance()
        
        # Initialize cache
        self.cache = {}
        self.cache_timestamps = {}
        
        # Load configuration
        self.config = self._load_configuration()
        
        # Initialize model registry
        self.model_registry = self._initialize_model_registry()
        
        # Initialize navigation map
        self.navigation = self._build_navigation_map()
        
        # Initialize context providers
        self.context_providers = []
        self._load_context_providers()
        
        print(f"ApplicationContextService initialized (version {self.CONTEXT_VERSION})")
    
    def _load_configuration(self) -> Dict[str, Any]:
        """
        Load configuration from file or database.
        
        Returns:
            Dictionary with configuration
        """
        try:
            # First try to load from database
            try:
                # Check if app_config model exists
                from app.models.app_config import AppConfig
                
                config_entry = AppConfig.query.filter_by(name="application_context_service").first()
                if config_entry and config_entry.config:
                    try:
                        return json.loads(config_entry.config)
                    except json.JSONDecodeError:
                        print("Invalid JSON in app_config.config")
            except (ImportError, AttributeError):
                # AppConfig model doesn't exist, skip this step
                pass
                
            # Fall back to file-based config
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'application_context.json')
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        return json.load(f)
            except Exception as e:
                print(f"Error loading config file: {str(e)}")
        except Exception as e:
            print(f"Error loading configuration: {str(e)}")
        
        # Default configuration if nothing else works
        return {
            'max_tokens': 2000,
            'sections': {
                'world_context': {'priority': 1, 'max_percent': 40},
                'scenario_context': {'priority': 2, 'max_percent': 30},
                'navigation': {'priority': 3, 'max_percent': 10},
                'entities': {'priority': 4, 'max_percent': 20}
            },
            'context_providers': {
                'default': {'enabled': True}
            },
            'caching': {
                'enabled': True,
                'ttl_seconds': 300
            },
            'schema_version': self.CONTEXT_VERSION
        }
    
    def _initialize_model_registry(self) -> Dict[str, Type]:
        """
        Initialize registry of models for dynamic entity handling.
        
        Returns:
            Dictionary of model names to model classes
        """
        model_registry = {}
        
        # Import all models from app.models
        try:
            # Try to import SQLAlchemy Base
            try:
                from app.models.base import Base
                base_class = Base
            except ImportError:
                try:
                    # Try importing from app directly
                    from app import db
                    base_class = db.Model
                except (ImportError, AttributeError):
                    # If we can't find a base class, default to db.Model
                    base_class = db.Model
            
            # Register common models we know about
            models_to_register = [
                (World, 'world'),
                (Scenario, 'scenario'),
                (Character, 'character'),
                (Event, 'event'),
                (Action, 'action'),
                (Resource, 'resource'),
                (EntityTriple, 'entity_triple')
            ]
            
            for model_class, name in models_to_register:
                model_registry[name.lower()] = model_class
            
            # Try to discover additional models
            try:
                # Import models module
                import app.models as models_module
                
                # Get all attributes that could be modules
                for module_name in dir(models_module):
                    if module_name.startswith('_'):
                        continue
                        
                    try:
                        module_attr = getattr(models_module, module_name)
                        
                        # If it's a module, look for classes
                        if inspect.ismodule(module_attr):
                            for attr_name in dir(module_attr):
                                if attr_name.startswith('_'):
                                    continue
                                    
                                try:
                                    attr = getattr(module_attr, attr_name)
                                    
                                    # Check if it's a class and a SQLAlchemy model
                                    if (inspect.isclass(attr) and 
                                        attr != base_class and 
                                        issubclass(attr, base_class)):
                                        
                                        model_registry[attr_name.lower()] = attr
                                        print(f"Discovered model: {attr_name}")
                                except (AttributeError, TypeError):
                                    continue
                    except (AttributeError, ImportError):
                        continue
            except ImportError:
                # app.models doesn't exist as a package
                pass
        except Exception as e:
            print(f"Error initializing model registry: {str(e)}")
        
        return model_registry
    
    def _build_navigation_map(self) -> Dict[str, Any]:
        """
        Build a map of available navigation paths in the application.
        
        Returns:
            Dictionary of navigation paths
        """
        navigation = {}
        
        # Try to extract routes from Flask's URL map
        try:
            from app import app
            
            if hasattr(app, 'url_map'):
                for rule in app.url_map.iter_rules():
                    # Skip static routes and other non-user facing routes
                    if 'static' in rule.endpoint or rule.endpoint.startswith('_'):
                        continue
                        
                    # Get blueprint and endpoint name
                    if '.' in rule.endpoint:
                        blueprint, endpoint = rule.endpoint.split('.', 1)
                    else:
                        blueprint, endpoint = None, rule.endpoint
                        
                    # Get details from rule
                    url = str(rule)
                    methods = list(rule.methods - {'HEAD', 'OPTIONS'})
                    
                    # Extract parameters
                    params = [p for p in rule.arguments]
                    
                    # Determine section based on blueprint
                    section = blueprint or 'main'
                    
                    # Initialize section if needed
                    if section not in navigation:
                        navigation[section] = {
                            'url': f"/{section}" if section != 'main' else '/',
                            'description': f"{section.title()} section",
                            'actions': {}
                        }
                        
                    # Add action
                    navigation[section]['actions'][endpoint] = {
                        'url': url,
                        'method': '/'.join(methods),
                        'params': params
                    }
                
                print(f"Discovered {len(navigation)} navigation sections from Flask URL map")
                return navigation
        except (ImportError, AttributeError) as e:
            print(f"Could not extract routes from Flask URL map: {str(e)}")
        
        # Fallback to hardcoded navigation
        navigation = {
            'home': {
                'url': '/',
                'description': 'Main application dashboard'
            },
            'worlds': {
                'url': '/worlds',
                'description': 'List of ethical worlds',
                'actions': {
                    'view': {'url': '/worlds/{id}', 'params': ['id']},
                    'create': {'url': '/worlds/create', 'method': 'GET/POST'},
                    'edit': {'url': '/worlds/{id}/edit', 'params': ['id'], 'method': 'GET/POST'},
                    'delete': {'url': '/worlds/{id}/delete', 'params': ['id'], 'method': 'POST'}
                }
            },
            'scenarios': {
                'url': '/scenarios',
                'description': 'List of ethical scenarios',
                'actions': {
                    'view': {'url': '/scenarios/{id}', 'params': ['id']},
                    'create': {'url': '/scenarios/create', 'method': 'GET/POST'},
                    'edit': {'url': '/scenarios/{id}/edit', 'params': ['id'], 'method': 'GET/POST'},
                    'delete': {'url': '/scenarios/{id}/delete', 'params': ['id'], 'method': 'POST'}
                }
            },
            'characters': {
                'url': '/characters',
                'description': 'List of characters in scenarios',
                'actions': {
                    'view': {'url': '/characters/{id}', 'params': ['id']},
                    'create': {'url': '/characters/create', 'method': 'GET/POST'},
                    'edit': {'url': '/characters/{id}/edit', 'params': ['id'], 'method': 'GET/POST'},
                    'delete': {'url': '/characters/{id}/delete', 'params': ['id'], 'method': 'POST'}
                }
            },
            'agent': {
                'url': '/agent',
                'description': 'AI agent for ethical decision analysis',
                'actions': {
                    'send_message': {'url': '/agent/api/message', 'method': 'POST'},
                    'get_options': {'url': '/agent/api/options', 'method': 'GET'},
                    'reset': {'url': '/agent/api/reset', 'method': 'POST'},
                    'get_guidelines': {'url': '/agent/api/guidelines', 'method': 'GET'}
                }
            }
        }
        
        print("Using hardcoded navigation map")
        return navigation
    
    def _load_context_providers(self) -> None:
        """Load context providers from the providers directory."""
        # Always add the default provider
        self.context_providers.append(DefaultContextProvider(self))
        
        # Load additional providers from the providers directory
        try:
            # Get providers directory
            providers_dir = os.path.join(os.path.dirname(__file__), 'context_providers')
            
            # Skip if directory doesn't exist
            if not os.path.exists(providers_dir):
                print(f"Context providers directory not found: {providers_dir}")
                return
            
            # Get all Python files in the directory
            for filename in os.listdir(providers_dir):
                if filename.endswith('.py') and not filename.startswith('_'):
                    module_name = filename[:-3]  # Remove .py extension
                    
                    # Skip base_provider and default_provider (already loaded)
                    if module_name in ['base_provider', 'default_provider']:
                        continue
                    
                    try:
                        # Import the module
                        module = importlib.import_module(f'app.services.context_providers.{module_name}')
                        
                        # Find provider classes
                        for name, obj in inspect.getmembers(module, inspect.isclass):
                            if issubclass(obj, ContextProvider) and obj != ContextProvider:
                                # Check if provider is enabled in config
                                provider_name = name.lower().replace('contextprovider', '')
                                is_enabled = self.config.get('context_providers', {}).get(provider_name, {}).get('enabled', False)
                                
                                if is_enabled:
                                    # Create instance and register
                                    provider = obj(self)
                                    self.context_providers.append(provider)
                                    print(f"Registered context provider: {name}")
                                else:
                                    print(f"Skipping disabled provider: {name}")
                    except Exception as e:
                        print(f"Error loading context provider {module_name}: {str(e)}")
        except Exception as e:
            print(f"Error loading context providers: {str(e)}")
    
    def get_full_context(self, world_id=None, scenario_id=None, query=None) -> Dict[str, Any]:
        """
        Get the full application context based on world, scenario, and query.
        
        Args:
            world_id: Optional ID of the current world
            scenario_id: Optional ID of the current scenario
            query: Optional user query to adapt context
            
        Returns:
            Complete context as a structured dictionary
        """
        # Create cache key
        cache_key = f"context_{world_id}_{scenario_id}_{query}"
        
        # Check cache
        if self.config.get('caching', {}).get('enabled', False):
            if cache_key in self.cache:
                # Check if cache is still valid
                cache_time = self.cache_timestamps.get(cache_key, 0)
                ttl = self.config.get('caching', {}).get('ttl_seconds', 300)
                
                if time.time() - cache_time < ttl:
                    print(f"Using cached context for {cache_key}")
                    return self.cache[cache_key]
        
        # Create request context
        request_context = {
            'world_id': world_id,
            'scenario_id': scenario_id,
            'query': query
        }
        
        # Get base context
        context = {
            'application_state': self._get_application_state(),
            'navigation': self.navigation
        }
        
        # Add context from providers
        for provider in self.context_providers:
            try:
                provider_name = provider.__class__.__name__.lower().replace('contextprovider', '')
                provider_context = provider.get_context(request_context)
                
                if provider_context:
                    context[f'{provider_name}_context'] = provider_context
            except Exception as e:
                print(f"Error getting context from provider {provider.__class__.__name__}: {str(e)}")
        
        # Store in cache
        if self.config.get('caching', {}).get('enabled', False):
            self.cache[cache_key] = context
            self.cache_timestamps[cache_key] = time.time()
        
        return context
    
    def format_context_for_llm(self, context: Dict[str, Any], max_tokens=None) -> str:
        """
        Format the context for LLM consumption, prioritizing information
        within token limits.
        
        Args:
            context: Full context dictionary
            max_tokens: Maximum tokens to include (overrides config)
            
        Returns:
            Formatted string context
        """
        max_tokens = max_tokens or self.config.get('max_tokens', 2000)
        
        # Start with application state (always include)
        formatted = self._format_application_state(context['application_state'])
        
        # Add navigation section
        if 'navigation' in context:
            formatted += "\n\n" + self._format_navigation(context['navigation'])
        
        # Estimate tokens so far
        tokens_used = self._estimate_tokens(formatted)
        tokens_remaining = max_tokens - tokens_used
        
        # Prioritize the rest of the content based on providers
        # Each provider can format its own context
        prioritized_sections = []
        
        for provider in self.context_providers:
            provider_name = provider.__class__.__name__.lower().replace('contextprovider', '')
            context_key = f'{provider_name}_context'
            
            if context_key in context and context[context_key]:
                # Get priority and max percentage for this section
                section_config = self.config.get('sections', {}).get(provider_name, {})
                priority = section_config.get('priority', 99)  # Default to low priority
                max_percent = section_config.get('max_percent', 20)  # Default to 20%
                
                # Format this section
                section_content = provider.format_context(context[context_key])
                section_tokens = self._estimate_tokens(section_content)
                
                # Calculate max tokens for this section
                max_section_tokens = int(max_tokens * max_percent / 100)
                
                # Truncate if needed
                if section_tokens > max_section_tokens:
                    section_content = self._truncate_context(section_content, max_section_tokens)
                    section_tokens = max_section_tokens
                
                # Add to prioritized sections
                prioritized_sections.append({
                    'content': section_content,
                    'tokens': section_tokens,
                    'priority': priority
                })
        
        # Sort by priority (lower number = higher priority)
        prioritized_sections.sort(key=lambda x: x['priority'])
        
        # Add sections until we reach token limit
        for section in prioritized_sections:
            if tokens_remaining >= section['tokens']:
                formatted += "\n\n" + section['content']
                tokens_remaining -= section['tokens']
            else:
                # Try to add a truncated version
                truncated = self._truncate_context(section['content'], tokens_remaining)
                formatted += "\n\n" + truncated
                break
        
        return formatted
    
    def _get_application_state(self) -> Dict[str, Any]:
        """Get the current state of the application."""
        return {
            'context_version': self.CONTEXT_VERSION,
            'worlds_count': World.query.count(),
            'scenarios_count': Scenario.query.count(),
            'characters_count': Character.query.count(),
            'triples_count': EntityTriple.query.count(),
            'timestamp': datetime.now().isoformat(),
            'providers': [p.__class__.__name__ for p in self.context_providers]
        }
    
    def _format_application_state(self, state: Dict[str, Any]) -> str:
        """Format application state for LLM."""
        return f"""APPLICATION STATE:
- Context schema version: {state['context_version']}
- Worlds: {state['worlds_count']}
- Scenarios: {state['scenarios_count']}
- Characters: {state['characters_count']}
- Entity Triples: {state['triples_count']}
- Timestamp: {state['timestamp']}"""
    
    def _format_navigation(self, navigation: Dict[str, Any]) -> str:
        """Format navigation for LLM."""
        text = "AVAILABLE NAVIGATION:\n"
        
        for section, data in navigation.items():
            text += f"- {section.upper()}: {data['url']} - {data['description']}\n"
            
            if 'actions' in data:
                text += "  Actions:\n"
                for action, action_data in data['actions'].items():
                    method = action_data.get('method', 'GET')
                    params = ', '.join(action_data.get('params', []))
                    params_text = f" (params: {params})" if params else ""
                    text += f"  - {action}: {action_data['url']} [{method}]{params_text}\n"
        
        return text
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate the number of tokens in a text string.
        This is a simplified estimator - approximately 4 chars per token for English.
        
        Args:
            text: Text to estimate
            
        Returns:
            Estimated token count
        """
        if not text:
            return 0
        
        # Simple estimation: ~4 characters per token for English text
        return len(text) // 4 + 1
    
    def _truncate_context(self, text: str, max_tokens: int) -> str:
        """
        Truncate context to fit within max_tokens.
        Tries to preserve section headers and structure.
        
        Args:
            text: Text to truncate
            max_tokens: Maximum tokens allowed
            
        Returns:
            Truncated text
        """
        if not text:
            return ""
        
        # Estimate current token count
        current_tokens = self._estimate_tokens(text)
        
        if current_tokens <= max_tokens:
            return text
        
        # Split text into sections by double newlines
        sections = text.split("\n\n")
        
        # Keep adding sections until we reach token limit
        result = []
        tokens_used = 0
        
        for section in sections:
            section_tokens = self._estimate_tokens(section)
            
            if tokens_used + section_tokens <= max_tokens:
                result.append(section)
                tokens_used += section_tokens
            else:
                # For the last section, try to include as much as possible
                remaining_tokens = max_tokens - tokens_used
                
                if remaining_tokens > 10:  # Only if we have meaningful space left
                    # Split by lines and add as many as will fit
                    lines = section.split("\n")
                    truncated_section = []
                    
                    for line in lines:
                        line_tokens = self._estimate_tokens(line)
                        
                        if tokens_used + line_tokens <= max_tokens:
                            truncated_section.append(line)
                            tokens_used += line_tokens
                        else:
                            break
                    
                    if truncated_section:
                        result.append("\n".join(truncated_section))
                
                # Add truncation indicator and break
                result.append("... (truncated)")
                break
        
        return "\n\n".join(result)
    
    def register_context_provider(self, provider_class: Type[ContextProvider]) -> bool:
        """
        Register a new context provider at runtime.
        
        Args:
            provider_class: Class of the provider to register
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not issubclass(provider_class, ContextProvider):
                return False
                
            # Create instance and register
            provider = provider_class(self)
            self.context_providers.append(provider)
            print(f"Dynamically registered context provider: {provider_class.__name__}")
            return True
        except Exception as e:
            print(f"Error registering context provider: {str(e)}")
            return False
    
    def update_configuration(self, new_config: Dict[str, Any]) -> bool:
        """
        Update the service configuration.
        
        Args:
            new_config: New configuration dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate configuration
            if not isinstance(new_config, dict):
                return False
                
            # Required fields
            required_fields = ['max_tokens', 'sections']
            for field in required_fields:
                if field not in new_config:
                    return False
            
            # Update configuration
            self.config = new_config
            
            # Try to save to database
            try:
                # Check if app_config model exists
                from app.models.app_config import AppConfig
                
                config_entry = AppConfig.query.filter_by(name="application_context_service").first()
                
                if config_entry:
                    config_entry.config = json.dumps(new_config)
                    config_entry.updated_at = datetime.now()
                else:
                    config_entry = AppConfig(
                        name="application_context_service",
                        config=json.dumps(new_config),
                        created_at=datetime.now(),
                        updated_at=datetime.now()
                    )
                    db.session.add(config_entry)
                    
                db.session.commit()
            except Exception as e:
                print(f"Error saving configuration to database: {str(e)}")
                
                # Try to save to file as fallback
                config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'application_context.json')
                with open(config_path, 'w') as f:
                    json.dump(new_config, f, indent=2)
            
            # Clear cache
            self.cache = {}
            self.cache_timestamps = {}
            
            return True
        except Exception as e:
            print(f"Error updating configuration: {str(e)}")
            return False
    
    def generate_schema_documentation(self) -> str:
        """
        Generate documentation of the current context schema.
        
        Returns:
            Markdown string with schema documentation
        """
        docs = f"""# Application Context Schema Documentation
Version: {self.CONTEXT_VERSION}
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Overview
This document describes the schema of the application context provided to the LLM.

"""
        
        # Document config
        docs += "## Configuration\n\n"
        docs += "```json\n"
        docs += json.dumps(self.config, indent=2)
        docs += "\n```\n\n"
        
        # Document navigation
        docs += "## Navigation Structure\n\n"
        for section, data in self.navigation.items():
            docs += f"### {section.title()}\n\n"
            docs += f"- URL: {data['url']}\n"
            docs += f"- Description: {data['description']}\n\n"
            
            if 'actions' in data:
                docs += "#### Actions\n\n"
                for action, action_data in data['actions'].items():
                    method = action_data.get('method', 'GET')
                    params = ', '.join(action_data.get('params', []))
                    params_text = f" (params: {params})" if params else ""
                    docs += f"- {action}: {action_data['url']} [{method}]{params_text}\n"
                docs += "\n"
        
        # Document registered models
        docs += "## Registered Models\n\n"
        for name, model in self.model_registry.items():
            docs += f"- {name}: {model.__name__}\n"
        docs += "\n"
        
        # Document context providers
        docs += "## Context Providers\n\n"
        for provider in self.context_providers:
            provider_name = provider.__class__.__name__
            docs += f"### {provider_name}\n\n"
            
            # Get docstring if available
            if provider.__class__.__doc__:
                docs += f"{provider.__class__.__doc__.strip()}\n\n"
        
        # Generate sample context
        docs += "## Example Context Format\n\n"
        docs += "```\n"
        sample_context = self.get_full_context()
        formatted_sample = self.format_context_for_llm(sample_context)
        # Truncate if too long
        if len(formatted_sample) > 1000:
            formatted_sample = formatted_sample[:1000] + "\n...(truncated)..."
        docs += formatted_sample
        docs += "\n```\n"
        
        return docs
