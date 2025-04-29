"""
Environment configuration loader.
This module detects the current environment and loads the appropriate configuration.
"""

import os
import importlib
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment detection
# Check if we're in GitHub Codespaces
if os.environ.get('CODESPACES', '').lower() == 'true':
    ENVIRONMENT = 'codespace'
    logger.info("Detected GitHub Codespaces environment")
# Check if we're in WSL
elif sys.platform == 'linux' and os.path.exists('/proc/version') and 'microsoft' in open('/proc/version').read().lower():
    ENVIRONMENT = 'wsl'
    logger.info("Detected WSL environment")
else:
    # Default to environment variable if set, otherwise development
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development').lower()
    logger.info(f"Using environment from configuration: {ENVIRONMENT}")

VALID_ENVIRONMENTS = ['development', 'production', 'wsl', 'codespace']

if ENVIRONMENT not in VALID_ENVIRONMENTS:
    logger.warning(f"Unknown environment: {ENVIRONMENT}, defaulting to development")
    ENVIRONMENT = 'development'

logger.info(f"Loading configuration for environment: {ENVIRONMENT}")

# Load environment-specific configuration
try:
    config_module = importlib.import_module(f"config.environments.{ENVIRONMENT}")

    # Export all settings from the environment module
    for setting in dir(config_module):
        if not setting.startswith('_'):  # Skip private attributes
            globals()[setting] = getattr(config_module, setting)

    # Mark with a constant that configuration was loaded successfully
    CONFIG_LOADED = True

except ImportError as e:
    logger.error(f"Failed to load configuration for {ENVIRONMENT}: {str(e)}")
    CONFIG_LOADED = False

# Export the detected environment
__all__ = ['ENVIRONMENT', 'CONFIG_LOADED'] + [
    setting for setting in dir()
    if not setting.startswith('_') and
       setting not in ['ENVIRONMENT', 'CONFIG_LOADED', 'VALID_ENVIRONMENTS',
                      'config_module', 'importlib', 'logging', 'logger', 'os', 'setting', 'sys']
]

# Create required directories
if 'LOG_DIR' in globals() and not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        logger.info(f"Created log directory: {LOG_DIR}")
    except PermissionError:
        logger.warning(f"Cannot create log directory {LOG_DIR}, insufficient permissions")

# Check for lock file path
if 'LOCK_FILE_PATH' in globals():
    lock_dir = os.path.dirname(LOCK_FILE_PATH)
    if lock_dir and lock_dir != '/tmp' and not os.path.exists(lock_dir):
        try:
            os.makedirs(lock_dir, exist_ok=True)
            logger.info(f"Created lock file directory: {lock_dir}")
        except PermissionError:
            logger.warning(f"Cannot create lock file directory {lock_dir}, insufficient permissions")

# Display loaded configuration if verbose logging is enabled
if globals().get('VERBOSE_LOGGING', False):
    logger.info("Loaded configuration settings:")
    for setting in __all__:
        if setting in globals():
            logger.info(f"  {setting} = {globals()[setting]}")
