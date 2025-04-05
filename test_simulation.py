#!/usr/bin/env python
"""
Test script to verify simulation functionality with the updated EmbeddingService.
"""

from app import create_app, db
from app.services.simulation_controller import SimulationController

def test_simulation():
    """Test running a simulation on scenario 1."""
    app = create_app()
    with app.app_context():
        print("Starting simulation for scenario 1...")
        try:
            controller = SimulationController(1)
            result = controller.start_simulation()
            print("Simulation started successfully!")
            print(f"Result: {result}")
            return True
        except Exception as e:
            print(f"Error in simulation: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == "__main__":
    test_simulation()
