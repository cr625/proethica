import os
from app import create_app

# Ensure production config
os.environ.setdefault('ENVIRONMENT', 'production')
os.environ.setdefault('CONFIG_MODULE', 'config')

# Gunicorn entry point
app = create_app('config')
