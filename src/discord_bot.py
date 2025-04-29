import discord
import logging
import asyncio
from typing import List

from .config_loader import get_config
from .database import Job, get_new_jobs_for_notification, mark_job_as_notified

log = logging.getLogger(__name__)

async def notify_new_jobs():
    """Fetches un-notified jobs and sends alerts to the configured Discord channel."""
    config = get_config()
    if not config:
        log.error("Config not loaded. Cannot send Discord notifications.")
        return

    discord_config = config.get('discord', {})
    if not discord_config.get('enabled', False):
        log.info("Discord notifications are disabled in the configuration.")
        return

    token = discord_config.get('token')
    channel_id = discord_config.get('channel_id')
    max_alerts = int(discord_config.get('max_alerts_per_run', 10))

    if not token or token == "YOUR_DISCORD_BOT_TOKEN":
        log.error("Discord bot token is missing or not set in config.yaml.")
        return
    if not channel_id or channel_id == "YOUR_DISCORD_CHANNEL_OR_USER_ID":
        log.error("Discord channel/user ID is missing or not set in config.yaml.")
        return

    try:
        channel_id = int(channel_id)
    except ValueError:
        log.error(f"Invalid Discord channel/user ID: {channel_id}. Must be an integer.")
        return

    # Fetch jobs that need notification
    # This needs to run within the bot's async context or be run separately
    # Let's fetch them outside the bot connection for simplicity first.
    jobs_to_notify: List[Job] = get_new_jobs_for_notification()

    if not jobs_to_notify:
        log.info("No new jobs found to notify about.")
        return

    log.info(f"Found {len(jobs_to_notify)} new jobs to potentially notify about.")

    # --- Connect to Discord and send --- 
    # Use intents to ensure member/channel fetching works reliably
    intents = discord.Intents.default()
    # No specific intents needed just to send messages to a known channel ID

    client = discord.Client(intents=intents)

    # Using @client.event decorator requires client.run(), but we want a one-off send.
    # We'll log in, send, and log out.

    try:
        # Define the sending logic within an async function for the client
        async def send_notifications():
            await client.wait_until_ready()
            log.info(f"Discord client ready. Logged in as {client.user}")

            try:
                channel = client.get_channel(channel_id) or await client.fetch_channel(channel_id)
                if not channel:
                    log.error(f"Could not find Discord channel with ID: {channel_id}")
                    return # Cannot proceed without channel

                if not isinstance(channel, (discord.TextChannel, discord.DMChannel, discord.GroupChannel, discord.Thread)):
                     log.error(f"Channel ID {channel_id} is not a valid text-based channel type.")
                     return

                log.info(f"Sending notifications to channel: #{channel.name if hasattr(channel, 'name') else channel_id}")
                sent_count = 0
                for job in jobs_to_notify:
                    if sent_count >= max_alerts:
                        log.warning(f"Reached maximum alert limit ({max_alerts}). Holding remaining notifications for next run.")
                        break

                    message = (
                        f"**{job.company}** - {job.title}\n"
                        f"*Location:* {job.location or 'N/A'}\n"
                        # f"*Posted:* {job.posted_date.strftime('%Y-%m-%d') if job.posted_date else 'N/A'}\n" # Add date if parsed
                        f"<{job.url}>"
                    )
                    try:
                        await channel.send(message)
                        log.info(f"Sent alert for job ID {job.id}: {job.title}")
                        # Mark as notified *after* successful send
                        if mark_job_as_notified(job.id):
                           log.debug(f"Successfully marked job ID {job.id} as notified in DB.")
                        else:
                             log.warning(f"Failed to mark job ID {job.id} as notified in DB after sending alert.")
                        sent_count += 1
                        await asyncio.sleep(1) # Small delay between messages to avoid rate limits
                    except discord.errors.Forbidden:
                        log.error(f"Permission error sending message to channel {channel_id}. Check bot permissions.")
                        # Stop trying if permissions fail
                        break
                    except discord.errors.HTTPException as e:
                        log.error(f"HTTP error sending message for job ID {job.id}: {e}")
                        # Optionally retry or just skip this one
                        await asyncio.sleep(2)
                    except Exception as e:
                         log.error(f"Unexpected error sending message for job ID {job.id}: {e}")
                         await asyncio.sleep(2)

                log.info(f"Finished sending {sent_count} Discord notifications.")

            except discord.errors.NotFound:
                log.error(f"Discord channel with ID {channel_id} not found.")
            except discord.errors.Forbidden:
                log.error(f"Permission error fetching channel {channel_id}. Check bot permissions.")
            except Exception as e:
                log.error(f"An unexpected error occurred during Discord notification sending: {e}", exc_info=True)
            finally:
                # Ensure logout even if errors occur during sending
                if client.is_ready():
                    log.info("Closing Discord client connection.")
                    await client.close()

        # Run the client and the notification logic
        # We need to run this within an asyncio event loop
        # The main CLI is synchronous, so we manage the loop here.
        await client.login(token)
        await send_notifications() # This will run until client.close() is called inside it
        # client.run() blocks, login()+task is non-blocking if needed elsewhere

    except discord.errors.LoginFailure:
        log.error("Discord login failed. Check the bot token.")
    except Exception as e:
        log.error(f"An unexpected error occurred while setting up Discord client: {e}", exc_info=True)
        # Ensure logout if client exists and might be logged in partially
        if client and client.is_logged_in():
             try:
                 await client.close()
             except Exception as close_err:
                 log.error(f"Error closing potentially lingering Discord connection: {close_err}") 