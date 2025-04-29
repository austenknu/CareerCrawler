import logging
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz # Required for timezone handling with CronTrigger

from .config_loader import get_config
from .scraper import run_scraper
from .discord_bot import notify_new_jobs

log = logging.getLogger(__name__)

async def scheduled_job():
    """The function to be executed by the scheduler."""
    log.info("--- Running scheduled job: Starting scrape... ---")
    config = get_config()
    if not config:
        log.error("Scheduler cannot run job: Configuration not loaded.")
        return

    try:
        # Run the synchronous scraper function in the default executor
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, run_scraper)
        log.info("--- Scheduled job: Scrape finished. Checking notifications... ---")

        # Run the async notification function if enabled
        discord_config = config.get('discord', {})
        if discord_config.get('enabled', False):
            await notify_new_jobs()
            log.info("--- Scheduled job: Notifications finished. ---")
        else:
            log.info("--- Scheduled job: Discord notifications disabled. ---")

    except Exception as e:
        log.error(f"Error during scheduled job execution: {e}", exc_info=True)

    log.info("--- Scheduled job finished. ---")


def run_scheduler():
    """Initializes and starts the job scheduler."""
    config = get_config()
    if not config:
        log.error("Configuration not loaded. Cannot start scheduler.")
        return

    scrape_config = config.get('scraping', {})
    schedule_time_str = scrape_config.get('schedule_time') # Expects "HH:MM"

    if not schedule_time_str or len(schedule_time_str.split(':')) != 2:
        log.error(f"Invalid or missing 'schedule_time' in config: '{schedule_time_str}'. Expected format HH:MM. Scheduler not started.")
        return

    try:
        hour, minute = map(int, schedule_time_str.split(':'))
    except ValueError:
         log.error(f"Invalid time format in 'schedule_time': '{schedule_time_str}'. Use integers for HH and MM. Scheduler not started.")
         return

    scheduler = AsyncIOScheduler(timezone=str(pytz.utc)) # Use UTC internally
    log.info(f"Scheduling job to run daily at {hour:02d}:{minute:02d} system time (using UTC reference for scheduler).")

    try:
        scheduler.add_job(
            scheduled_job,
            trigger=CronTrigger(
                hour=hour,
                minute=minute,
                # timezone='Your/System/Timezone' # Optional: Specify system timezone if HH:MM isn't UTC
                # If not specified, it uses the scheduler's timezone (UTC here)
                # Ensure the time matches what the user expects in their local time!
            ),
            id='daily_scrape_job',
            name='Daily Career Crawl and Notify',
            replace_existing=True
        )
    except Exception as e:
         log.error(f"Failed to add job to scheduler: {e}", exc_info=True)
         return

    log.info("Starting scheduler. Press Ctrl+C to exit.")
    scheduler.start()

    # Keep the scheduler running in the foreground
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
    finally:
        scheduler.shutdown() 