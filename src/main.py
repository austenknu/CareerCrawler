import click
import logging
import sys
import os
import asyncio # Import asyncio

# Adjust path to import from src
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.config_loader import get_config, load_config
from src.utils import setup_logging
from src.database import init_db
from src.scraper import run_scraper
from src.discord_bot import notify_new_jobs # Import notification function
from src.dashboard import run_dashboard # Import dashboard runner
from src.scheduler import run_scheduler # Import scheduler runner
# from src.dashboard import run_dashboard

# Initialize logging -- BEFORE anything else tries to log
# We load config explicitly first in case it wasn't loaded due to import order
if get_config() is None:
    load_config()
setup_logging()

# Initialize Database
if not init_db():
    log.error("Database initialization failed. Exiting.")
    sys.exit(1)

log = logging.getLogger(__name__)


@click.group()
def cli():
    """Career Crawler Framework CLI"""
    config = get_config()
    if config is None:
        log.error("Configuration could not be loaded. Exiting.")
        sys.exit(1)
    log.debug("CLI started.")


@cli.command()
def scrape():
    """Run the job scraper once, then send Discord notifications if enabled."""
    config = get_config()
    run_scraper()

    # After scraping, attempt to send notifications
    discord_config = config.get('discord', {})
    if discord_config.get('enabled', False):
        log.info("Scraping finished. Checking for and sending Discord notifications...")
        try:
            # Run the async notification function
            asyncio.run(notify_new_jobs())
        except Exception as e:
            log.error(f"An error occurred during Discord notification: {e}", exc_info=True)
    else:
        log.info("Discord notifications are disabled. Skipping notification step.")


@cli.command()
def dashboard():
    """Run the web dashboard."""
    config = get_config()
    # Check enabled status before calling run_dashboard
    if not config.get('dashboard', {}).get('enabled', False):
        log.warning("Dashboard is disabled in the configuration. Exiting.")
        print("Dashboard is disabled in config.yaml.")
        sys.exit(0)

    # Call the actual dashboard runner function
    run_dashboard()
    # Logging is handled within run_dashboard


@cli.command()
def schedule():
    """Run the scraper on the schedule defined in config.yaml."""
    log.info("Starting scheduler...")
    run_scheduler()
    # Note: run_scheduler() will block until interrupted (Ctrl+C)


if __name__ == '__main__':
    cli() 