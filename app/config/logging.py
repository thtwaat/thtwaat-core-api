"""
app/config/logging.py

Configures structured logging for the application.
"""
import logging
import sys

def configure_logging():
    from app.config.settings import settings
    import pythonjsonlogger.jsonlogger as jsonlogger
    
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.app_env == "production":
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s'
        )
    else:
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Set levels for noisy libraries if needed
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
