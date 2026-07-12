"""NightDesk application package.

Single responsibility: mark ``app`` as an importable Python package and ensure
environment variables from a local ``.env`` file are loaded before any submodule
reads ``os.environ`` (submodules read config at import time, so this must run first).
"""
from dotenv import load_dotenv

load_dotenv()
