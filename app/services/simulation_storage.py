"""
Simulation Storage Service for the AI Ethical Decision-Making Simulator.

This module provides a storage mechanism for simulation states to avoid
storing large amounts of data in session cookies. It uses a combination of
in-memory storage and session data to ensure persistence across server restarts.
"""

import logging
import uuid
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from flask import session

# Set up logging
logger = logging.getLogger(__name__)

class SimulationStorage:
    """
    A storage service for simulation states.
    
    This class provides methods to store and retrieve simulation states,
    with automatic cleanup of old states and fallback to session data
    for persistence across server restarts.
    """
    
    # Class-level storage
    _states = {}
    _expiry_times = {}
    
    # Default expiry time (30 minutes)
    DEFAULT_EXPIRY = timedelta(minutes=30)
    
    @classmethod
    def store_state(cls, state: Dict[str, Any], session_id: Optional[str] = None) -> str:
        """
        Store a simulation state and return a session ID.
        
        Args:
            state: The simulation state to store
            session_id: Optional existing session ID to update
            
        Returns:
            Session ID for retrieving the state
        """
        # Generate a new session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Store the state in memory
        cls._states[session_id] = state
        
        # Set expiry time
        cls._expiry_times[session_id] = datetime.now() + cls.DEFAULT_EXPIRY
        
        # Also store a minimal version in the session for fallback
        if 'simulation' in session:
            session['simulation']['last_state'] = {
                'scenario_id': state.get('scenario_id'),
                'current_event_index': state.get('current_event_index', 0),
                'events': state.get('events', []),
                'decision_history': state.get('decision_history', [])
            }
            session.modified = True
        
        # Clean up old states
        cls._cleanup()
        
        logger.debug(f"Stored simulation state with session ID: {session_id}")
        return session_id
    
    @classmethod
    def get_state(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a simulation state by session ID.
        
        Args:
            session_id: The session ID to retrieve
            
        Returns:
            The simulation state, or None if not found
        """
        # Check if the session ID exists in memory
        if session_id in cls._states:
            # Check if the session has expired
            if datetime.now() > cls._expiry_times.get(session_id, datetime.min):
                logger.warning(f"Simulation session expired for session ID: {session_id}")
                cls._remove_state(session_id)
            else:
                # Extend the expiry time
                cls._expiry_times[session_id] = datetime.now() + cls.DEFAULT_EXPIRY
                logger.debug(f"Retrieved simulation state from memory for session ID: {session_id}")
                return cls._states[session_id]
        
        # If not in memory, try to recover from session
        if 'simulation' in session and session['simulation'].get('session_id') == session_id:
            if 'last_state' in session['simulation']:
                logger.info(f"Recovering simulation state from session for session ID: {session_id}")
                recovered_state = session['simulation']['last_state']
                # Store it back in memory for future use
                cls._states[session_id] = recovered_state
                cls._expiry_times[session_id] = datetime.now() + cls.DEFAULT_EXPIRY
                return recovered_state
        
        logger.warning(f"Simulation state not found for session ID: {session_id}")
        return None
    
    @classmethod
    def remove_state(cls, session_id: str) -> None:
        """
        Remove a simulation state by session ID.
        
        Args:
            session_id: The session ID to remove
        """
        cls._remove_state(session_id)
    
    @classmethod
    def _remove_state(cls, session_id: str) -> None:
        """
        Internal method to remove a simulation state.
        
        Args:
            session_id: The session ID to remove
        """
        if session_id in cls._states:
            del cls._states[session_id]
        
        if session_id in cls._expiry_times:
            del cls._expiry_times[session_id]
        
        logger.debug(f"Removed simulation state for session ID: {session_id}")
    
    @classmethod
    def _cleanup(cls) -> None:
        """
        Clean up expired simulation states.
        """
        now = datetime.now()
        expired_ids = [
            session_id for session_id, expiry_time in cls._expiry_times.items()
            if now > expiry_time
        ]
        
        for session_id in expired_ids:
            cls._remove_state(session_id)
        
        if expired_ids:
            logger.debug(f"Cleaned up {len(expired_ids)} expired simulation states")
