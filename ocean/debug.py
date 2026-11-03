"""Debug mode configuration for the ocean module."""

import os

# Debug flags
DEBUG_MODE = os.getenv("DEBUG_MODE", "0")
DEBUG_FISH_ONLY = DEBUG_MODE == "1"
DEBUG_SHOW_BOUNDS = DEBUG_MODE == "2"
