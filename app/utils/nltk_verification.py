"""
Utility to verify that required NLTK resources are available.
"""
import nltk
import logging

logger = logging.getLogger(__name__)

def verify_nltk_resources():
    """
    Verify that required NLTK resources are available.

    Raises:
        RuntimeError: If any required resources are missing
    """
    required_resources = {
        'punkt': 'tokenizers/punkt',
        'stopwords': 'corpora/stopwords'
    }

    missing = []

    for name, path in required_resources.items():
        try:
            nltk.data.find(path)
        except LookupError:
            missing.append(name)

    if missing:
        error_msg = (
            f"Missing required NLTK resources: {', '.join(missing)}. "
            f"Please run 'python scripts/setup_nltk_resources.py' to install them."
        )
        print(f"\nNLTK Setup Required: {error_msg}\n")
        raise RuntimeError(error_msg)

    return True
