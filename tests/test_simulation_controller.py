"""
Tests for the SimulationController class.
"""

import unittest
from datetime import datetime, timedelta
import json
from app import create_app, db
from app.models import Scenario, Character, Event, Action, SimulationSession
from app.services.simulation_controller import SimulationController

class TestSimulationController(unittest.TestCase):
    """Test cases for the SimulationController class."""
    
    def setUp(self):
        """Set up test environment."""
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self._create_test_data()
    
    def tearDown(self):
        """Clean up test environment."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def _create_test_data(self):
        """Create test data for the tests."""
        # Create a test scenario
        self.scenario = Scenario(
            name='Test Scenario',
            description='A test scenario for unit tests',
            world_id=1  # Assuming world_id 1 exists
        )
        db.session.add(self.scenario)
        db.session.flush()
        
        # Create test characters
        self.character1 = Character(
            name='Character 1',
            role='Engineer',
            scenario_id=self.scenario.id
        )
        self.character2 = Character(
            name='Character 2',
            role='Manager',
            scenario_id=self.scenario.id
        )
        db.session.add_all([self.character1, self.character2])
        db.session.flush()
        
        # Create test events
        now = datetime.now()
        self.event1 = Event(
            description='Event 1',
            event_time=now,
            scenario_id=self.scenario.id,
            character_id=self.character1.id
        )
        self.event2 = Event(
            description='Event 2',
            event_time=now + timedelta(hours=1),
            scenario_id=self.scenario.id,
            character_id=self.character2.id
        )
        
        # Create a test action (decision point)
        self.action1 = Action(
            name='Decision 1',
            description='A test decision',
            scenario_id=self.scenario.id,
            character_id=self.character1.id,
            action_time=now + timedelta(hours=2),
            is_decision=True,
            options=['Option 1', 'Option 2', 'Option 3']
        )
        db.session.add_all([self.event1, self.event2, self.action1])
        
        # Create an event for the action
        self.event3 = Event(
            description='Decision point: Decision 1',
            event_time=now + timedelta(hours=2),
            scenario_id=self.scenario.id,
            character_id=self.character1.id,
            action_id=self.action1.id
        )
        db.session.add(self.event3)
        
        db.session.commit()
    
    def test_initialization(self):
        """Test initialization of SimulationController."""
        controller = SimulationController(self.scenario.id)
        self.assertEqual(controller.scenario.id, self.scenario.id)
        self.assertIsNone(controller.selected_character)
        self.assertEqual(controller.perspective, 'specific')
        
        # Test with selected character
        controller = SimulationController(self.scenario.id, self.character1.id)
        self.assertEqual(controller.selected_character.id, self.character1.id)
        
        # Test with invalid scenario
        with self.assertRaises(ValueError):
            SimulationController(9999)  # Non-existent scenario ID
        
        # Test with invalid character
        with self.assertRaises(ValueError):
            SimulationController(self.scenario.id, 9999)  # Non-existent character ID
    
    def test_initialize_simulation(self):
        """Test initialization of simulation state."""
        controller = SimulationController(self.scenario.id, self.character1.id)
        initial_state = controller.initialize_simulation()
        
        # Check basic state properties
        self.assertEqual(initial_state['scenario_id'], self.scenario.id)
        self.assertEqual(initial_state['scenario_name'], self.scenario.name)
        self.assertEqual(initial_state['selected_character_id'], self.character1.id)
        self.assertEqual(initial_state['perspective'], 'specific')
        
        # Check events
        self.assertEqual(len(initial_state['events']), 3)
        self.assertEqual(initial_state['current_event_index'], 0)
        
        # Check character states
        self.assertEqual(len(initial_state['character_states']), 2)
        self.assertIn(self.character1.id, initial_state['character_states'])
        self.assertIn(self.character2.id, initial_state['character_states'])
        
        # Check session data recording
        self.assertEqual(len(controller.session_data['states']), 1)
        self.assertEqual(len(controller.session_data['timestamps']), 1)
    
    def test_process_decision(self):
        """Test processing a decision."""
        controller = SimulationController(self.scenario.id, self.character1.id)
        initial_state = controller.initialize_simulation()
        
        # Advance to the decision point (event3)
        controller.current_state['current_event_index'] = 2  # Index of event3
        
        # Process a decision
        decision_data = {
            'option_id': 1,
            'character_id': self.character1.id
        }
        
        next_state, evaluation = controller.process_decision(decision_data)
        
        # Check that the state advanced
        self.assertEqual(next_state['current_event_index'], 3)
        
        # Check that the decision and evaluation were recorded
        self.assertEqual(len(controller.session_data['decisions']), 1)
        self.assertEqual(len(controller.session_data['evaluations']), 1)
        self.assertEqual(controller.session_data['decisions'][0]['option_id'], 1)
        
        # Check that the evaluation has the expected structure
        self.assertIn('raw_evaluation', evaluation)
        self.assertIn('structured_evaluation', evaluation)
    
    def test_save_session(self):
        """Test saving a simulation session."""
        controller = SimulationController(self.scenario.id, self.character1.id)
        controller.initialize_simulation()
        
        # Save the session
        session_id = controller.save_session()
        
        # Check that the session was saved to the database
        session = SimulationSession.query.get(session_id)
        self.assertIsNotNone(session)
        self.assertEqual(session.scenario_id, self.scenario.id)
        
        # Check that the session data was saved correctly
        session_data = session.session_data
        self.assertIn('states', session_data)
        self.assertIn('timestamps', session_data)
        self.assertEqual(len(session_data['states']), 1)

if __name__ == '__main__':
    unittest.main()
