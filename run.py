import os
import argparse
from app import create_app

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Run the AI Ethical DM application')
parser.add_argument('--port', type=int, default=5001, help='Port to run the server on')
args = parser.parse_args()

# Create app instance
app = create_app(os.getenv('FLASK_ENV', 'default'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=args.port, debug=True)
