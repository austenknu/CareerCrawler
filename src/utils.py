import logging
import os
import sys
from typing import Optional

from .config_loader import get_config

def setup_logging() -> None:
    """Configures logging based on the settings in config.yaml."""
    config = get_config()
    if not config or 'logging' not in config:
        # Default basic logging if config is missing or incomplete
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            stream=sys.stdout)
        logging.warning("Logging configuration not found or incomplete. Using default stdout INFO logging.")
        return

    log_config = config['logging']
    log_level_str = log_config.get('log_level', 'INFO').upper()
    log_file = log_config.get('log_file', 'scraper.log')

    log_level = getattr(logging, log_level_str, logging.INFO)

    # Ensure log directory exists (if log_file path includes directories)
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Error creating log directory '{log_dir}': {e}")
            # Fallback to stdout logging
            logging.basicConfig(level=log_level,
                                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                                stream=sys.stdout)
            logging.error(f"Could not create log directory. Logging to stdout.")
            return

    # Configure logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    log_handlers = []

    # File Handler
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(logging.Formatter(log_format))
        log_handlers.append(file_handler)
    except Exception as e:
        print(f"Error setting up file logger for '{log_file}': {e}")

    # Console Handler (always log to console as well, maybe at a different level?)
    # For now, matching file level.
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(log_format))
    log_handlers.append(console_handler)

    logging.basicConfig(level=log_level,
                        format=log_format, # BasicConfig sets default format, handlers override
                        handlers=log_handlers,
                        force=True # Override any existing config
                        )

    logging.info(f"Logging configured. Level: {log_level_str}, File: '{os.path.abspath(log_file) if log_handlers else 'None'}'") 