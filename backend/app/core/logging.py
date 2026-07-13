import logging
import sys
from app.core.config import settings

def setup_logging() -> None:
    """Sets up global application logging."""
    # Retrieve active log level from settings
    log_level_name = settings.LOG_LEVEL.upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Clear root logger handlers to prevent duplicates
    root = logging.getLogger()
    if root.handlers:
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    # Set root logger level
    root.setLevel(log_level)

    # Create console handler with format
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Log configuration success
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Level: {log_level_name}")
