import yaml
import os
from typing import Dict, Any, Optional

CONFIG_FILENAME = "config.yaml"
TEMPLATE_FILENAME = "config.yaml.template"

def load_config() -> Optional[Dict[str, Any]]:
    """Loads configuration from config.yaml.

    Looks for config.yaml in the project root. If not found,
    prints an error message pointing to the template file.

    Returns:
        A dictionary containing the configuration, or None if the file
        is not found or cannot be parsed.
    """
    config_path = os.path.join(os.path.dirname(__file__), '..', CONFIG_FILENAME)
    template_path = os.path.join(os.path.dirname(__file__), '..', TEMPLATE_FILENAME)

    if not os.path.exists(config_path):
        print(f"Error: Configuration file '{CONFIG_FILENAME}' not found.")
        print(f"Please rename or copy '{TEMPLATE_FILENAME}' to '{CONFIG_FILENAME}'")
        print(f"and fill in your details.")
        return None

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as e:
        print(f"Error parsing configuration file '{config_path}': {e}")
        return None
    except Exception as e:
        print(f"Error loading configuration file '{config_path}': {e}")
        return None

# Load config once on import
config = load_config()

def get_config() -> Optional[Dict[str, Any]]:
    """Returns the loaded configuration dictionary."""
    return config 