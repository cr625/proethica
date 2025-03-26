"""
Simulation Storage Service for the AI Ethical Decision-Making Simulator.

This module provides a storage mechanism for simulation states using the database.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from flask_login import current_user

from app import db
from app.models.simulation_state import SimulationState

# Set up logging
logger = logging.getLogger(__name__)

class SimulationStorage:
    """
    A storage service for simulation states using the database.
    
    This class provides methods to store and retrieve simulation states,
    with automatic cleanup of old states.
    """
    
    # Default expiry time (30 minutes)
    DEFAULT_EXPIRY = timedelta(minutes=30)
    
    @classmethod
    def store_state(cls, state: Dict[str, Any], session_id: Optional[str] = None) -> str:
        """
        Store a simulation state in the database and return a session ID.
        
        Args:
            state: The simulation state to store
            session_id: Optional existing session ID to update
            
        Returns:
            Session ID for retrieving the state
        """
        # Generate a new session ID if not provided
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Calculate expiry time
        expires_at = datetime.utcnow() + cls.DEFAULT_EXPIRY
        
        # Check if a state with this session_id already exists
        existing_state = SimulationState.query.filter_by(session_id=session_id).first()
        
        if existing_state:
            # Update existing state
            existing_state.state_data = state
            existing_state.current_event_index = state.get('current_event_index', 0)
            existing_state.decisions = state.get('decision_history', [])
            existing_state.updated_at = datetime.utcnow()
            existing_state.expires_at = expires_at
            db.session.commit()
            logger.info(f"Updated simulation state with session ID: {session_id}")
        else:
            # Create new state
            user_id = current_user.id if current_user and current_user.is_authenticated else None
            
            new_state = SimulationState(
                session_id=session_id,
                scenario_id=state.get('scenario_id'),
                user_id=user_id,
                current_event_index=state.get('current_event_index', 0),
                decisions=state.get('decision_history', []),
                state_data=state,
                expires_at=expires_at
            )
            
            db.session.add(new_state)
            db.session.commit()
            logger.info(f"Stored new simulation state with session ID: {session_id}")
        
        # Clean up old states
        cls._cleanup()
        
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
        # Find the state in the database
        state_record = SimulationState.query.filter_by(session_id=session_id).first()
        
        if not state_record:
            logger.warning(f"Simulation state not found for session ID: {session_id}")
            return None
        
        # Check if the state has expired
        if state_record.expires_at and datetime.utcnow() > state_record.expires_at:
            logger.warning(f"Simulation session expired for session ID: {session_id}")
            cls.remove_state(session_id)
            return None
        
        # Extend the expiry time
        state_record.expires_at = datetime.utcnow() + cls.DEFAULT_EXPIRY
        db.session.commit()
        
        logger.info(f"Retrieved simulation state for session ID: {session_id}")
        return state_record.state_data
    
    @classmethod
    def remove_state(cls, session_id: str) -> None:
        """
        Remove a simulation state by session ID.
        
        Args:
            session_id: The session ID to remove
        """
        state_record = SimulationState.query.filter_by(session_id=session_id).first()
        
        if state_record:
            db.session.delete(state_record)
            db.session.commit()
            logger.info(f"Removed simulation state for session ID: {session_id}")
    
    @classmethod
    def _cleanup(cls) -> None:
        """
        Clean up expired simulation states.
        """
        expired_states = SimulationState.query.filter(
            SimulationState.expires_at < datetime.utcnow()
        ).all()
        
        for state in expired_states:
            db.session.delete(state)
        
        if expired_states:
            db.session.commit()
            logger.debug(f"Cleaned up {len(expired_states)} expired simulation states")
