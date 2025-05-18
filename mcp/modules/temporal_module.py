#!/usr/bin/env python3
"""
Temporal Module for the Unified Ontology Server

This module provides temporal functionality for the Unified Ontology Server,
including timeline generation, temporal context, and temporal relations.
"""

import logging
import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional, Any, Union

# Add the project root to the path to import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from mcp.modules.base_module import MCPBaseModule

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TemporalModule")

class TemporalModule(MCPBaseModule):
    """
    Module for temporal functionality in the Unified Ontology Server.

    This module integrates the temporal functionality previously provided by
    add_temporal_functionality.py into the modular architecture of the
    Unified Ontology Server.
    """

    def __init__(self):
        """Initialize the temporal module."""
        super().__init__(name="temporal")
        
    @property
    def description(self) -> str:
        """Get the description of this module."""
        return "Temporal functionality for ontology"
    
    def _register_tools(self):
        """Register all tools provided by this module."""
        self.register_tool(
            name="get_timeline",
            description="Get a complete timeline for a scenario",
            handler=self.get_timeline,
            input_schema={
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "integer",
                        "description": "ID of the scenario"
                    }
                },
                "required": ["scenario_id"]
            }
        )
        
        self.register_tool(
            name="get_temporal_context",
            description="Get formatted temporal context for Claude",
            handler=self.get_temporal_context,
            input_schema={
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "integer",
                        "description": "ID of the scenario"
                    }
                },
                "required": ["scenario_id"]
            }
        )
        
        self.register_tool(
            name="get_events_in_timeframe",
            description="Get events within a specific timeframe",
            handler=self.get_events_in_timeframe,
            input_schema={
                "type": "object",
                "properties": {
                    "start_time": {
                        "type": "string",
                        "description": "Start time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time in ISO format (YYYY-MM-DDTHH:MM:SS)"
                    },
                    "scenario_id": {
                        "type": "integer",
                        "description": "ID of the scenario"
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity to filter by (optional)"
                    }
                },
                "required": ["start_time", "end_time", "scenario_id"]
            }
        )
        
        self.register_tool(
            name="get_temporal_sequence",
            description="Get a sequence of events in temporal order",
            handler=self.get_temporal_sequence,
            input_schema={
                "type": "object",
                "properties": {
                    "scenario_id": {
                        "type": "integer",
                        "description": "ID of the scenario"
                    },
                    "entity_type": {
                        "type": "string",
                        "description": "Type of entity to filter by (optional)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of events to return (optional)"
                    }
                },
                "required": ["scenario_id"]
            }
        )
        
        self.register_tool(
            name="get_temporal_relation",
            description="Get triples with a specific temporal relation to a given triple",
            handler=self.get_temporal_relation,
            input_schema={
                "type": "object",
                "properties": {
                    "triple_id": {
                        "type": "integer",
                        "description": "ID of the triple"
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Type of temporal relation (before, after, during, etc.)"
                    }
                },
                "required": ["triple_id", "relation_type"]
            }
        )
        
        self.register_tool(
            name="create_temporal_relation",
            description="Create a temporal relation between two triples",
            handler=self.create_temporal_relation,
            input_schema={
                "type": "object",
                "properties": {
                    "from_triple_id": {
                        "type": "integer",
                        "description": "ID of the source triple"
                    },
                    "to_triple_id": {
                        "type": "integer",
                        "description": "ID of the target triple"
                    },
                    "relation_type": {
                        "type": "string",
                        "description": "Type of temporal relation (before, after, during, etc.)"
                    }
                },
                "required": ["from_triple_id", "to_triple_id", "relation_type"]
            }
        )
    
    def get_flask_app_context(self):
        """Get a Flask app context for database access."""
        try:
            from app import create_app
            return create_app()
        except ImportError as e:
            logger.error(f"Failed to import Flask app: {e}")
            return None
    
    async def get_timeline(self, params: Dict) -> Dict:
        """
        Get the complete timeline for a scenario.
        
        Args:
            params: Dictionary containing scenario_id
            
        Returns:
            Dictionary containing the timeline
        """
        try:
            scenario_id = params.get("scenario_id")
            
            app = self.get_flask_app_context()
            if not app:
                return {"error": "Failed to create Flask app context"}
            
            with app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                timeline = temporal_service.build_timeline(scenario_id)
                
                return {"timeline": timeline}
                
        except Exception as e:
            logger.error(f"Error building timeline: {str(e)}")
            return {"error": f"Error building timeline: {str(e)}"}
    
    async def get_temporal_context(self, params: Dict) -> Dict:
        """
        Get formatted temporal context for Claude.
        
        Args:
            params: Dictionary containing scenario_id
            
        Returns:
            Dictionary containing the temporal context
        """
        try:
            scenario_id = params.get("scenario_id")
            
            app = self.get_flask_app_context()
            if not app:
                return {"error": "Failed to create Flask app context"}
            
            with app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                context = temporal_service.get_temporal_context_for_claude(scenario_id)
                
                return {"context": context}
                
        except Exception as e:
            logger.error(f"Error getting temporal context: {str(e)}")
            return {"error": f"Error getting temporal context: {str(e)}"}
    
    async def get_events_in_timeframe(self, params: Dict) -> Dict:
        """
        Get events within a specific timeframe.
        
        Args:
            params: Dictionary containing start_time, end_time, scenario_id, entity_type
            
        Returns:
            Dictionary containing the events
        """
        try:
            start_time = params.get("start_time")
            end_time = params.get("end_time")
            scenario_id = params.get("scenario_id")
            entity_type = params.get("entity_type")
            
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
            except ValueError:
                return {"error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}
            
            app = self.get_flask_app_context()
            if not app:
                return {"error": "Failed to create Flask app context"}
            
            with app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                triples = temporal_service.find_triples_in_timeframe(
                    start_dt, end_dt, entity_type=entity_type, scenario_id=scenario_id
                )
                results = [triple.to_dict() for triple in triples]
                
                return {"events": results}
                
        except Exception as e:
            logger.error(f"Error finding events in timeframe: {str(e)}")
            return {"error": f"Error finding events in timeframe: {str(e)}"}
    
    async def get_temporal_sequence(self, params: Dict) -> Dict:
        """
        Get a sequence of events in temporal order.
        
        Args:
            params: Dictionary containing scenario_id, entity_type, limit
            
        Returns:
            Dictionary containing the sequence of events
        """
        try:
            scenario_id = params.get("scenario_id")
            entity_type = params.get("entity_type")
            limit = params.get("limit")
            
            app = self.get_flask_app_context()
            if not app:
                return {"error": "Failed to create Flask app context"}
            
            with app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                sequence = temporal_service.find_temporal_sequence(
                    scenario_id, entity_type=entity_type, limit=limit
                )
                results = [triple.to_dict() for triple in sequence]
                
                return {"sequence": results}
                
        except Exception as e:
            logger.error(f"Error getting temporal sequence: {str(e)}")
            return {"error": f"Error getting temporal sequence: {str(e)}"}
    
    async def get_temporal_relation(self, params: Dict) -> Dict:
        """
        Get triples with a specific temporal relation to a given triple.
        
        Args:
            params: Dictionary containing triple_id, relation_type
            
        Returns:
            Dictionary containing the related triples
        """
        try:
            triple_id = params.get("triple_id")
            relation_type = params.get("relation_type")
            
            app = self.get_flask_app_context()
            if not app:
                return {"error": "Failed to create Flask app context"}
            
            with app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                relations = temporal_service.find_temporal_relations(triple_id, relation_type)
                results = [triple.to_dict() for triple in relations]
                
                return {"relations": results}
                
        except Exception as e:
            logger.error(f"Error getting temporal relations: {str(e)}")
            return {"error": f"Error getting temporal relations: {str(e)}"}
    
    async def create_temporal_relation(self, params: Dict) -> Dict:
        """
        Create a temporal relation between two triples.
        
        Args:
            params: Dictionary containing from_triple_id, to_triple_id, relation_type
            
        Returns:
            Dictionary indicating success or failure
        """
        try:
            from_triple_id = params.get("from_triple_id")
            to_triple_id = params.get("to_triple_id")
            relation_type = params.get("relation_type")
            
            app = self.get_flask_app_context()
            if not app:
                return {"error": "Failed to create Flask app context"}
            
            with app.app_context():
                from app.services.temporal_context_service import TemporalContextService
                temporal_service = TemporalContextService()
                success = temporal_service.create_temporal_relation(
                    from_triple_id, to_triple_id, relation_type
                )
                
                if success:
                    return {"success": True}
                else:
                    return {"error": "Failed to create temporal relation"}
                    
        except Exception as e:
            logger.error(f"Error creating temporal relation: {str(e)}")
            return {"error": f"Error creating temporal relation: {str(e)}"}
    
    def shutdown(self):
        """Perform cleanup when shutting down the module."""
        logger.info("Shutting down TemporalModule")
