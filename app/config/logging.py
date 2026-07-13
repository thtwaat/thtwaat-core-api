"""
app/config/logging.py

Configures structured logging for the application.
"""
import logging
import sys

def configure_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # Set levels for noisy libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
