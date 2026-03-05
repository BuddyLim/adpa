import os

# Set env vars BEFORE any app imports happen
# This runs at module level during conftest.py import,
# which happens before test collection imports app modules
os.environ.setdefault("OPENAI_KEY", "test-key")
os.environ.setdefault("GCP_KEY", "test-key")
os.environ.setdefault("LOGFIRE_IGNORE_NO_CONFIG", "1")
