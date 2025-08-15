import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'app' can be imported
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Hermetic defaults for tests (avoid network/LLM/DB by default)
os.environ.setdefault("CONFIG_MODULE", "config")
os.environ.setdefault("FORCE_MOCK_LLM", "true")
os.environ.setdefault("USE_MOCK_FALLBACK", "true")
os.environ.setdefault("BYPASS_AUTH", "true")
os.environ.setdefault("DEBUG", "false")
# Point MCP to a closed port so connection check fails fast and uses mock
os.environ.setdefault("MCP_SERVER_URL", "http://127.0.0.1:9")
# Disable DB vector search by default in unit tests
os.environ.setdefault("USE_DB_VECTOR_SEARCH", "false")
