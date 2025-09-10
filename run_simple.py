#!/usr/bin/env python
"""
Run ProEthica with simplified configuration.
"""

import os

# Set environment variables
os.environ['USE_DATABASE_LANGEXTRACT_EXAMPLES'] = 'true'
os.environ['ENABLE_ONTOLOGY_DRIVEN_LANGEXTRACT'] = 'true'

from app import create_app

if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=False)