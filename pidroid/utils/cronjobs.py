import aiocron
import asyncio
import logging

from contextlib import suppress

from pidroid.client import Pidroid

logger = logging.getLogger("Pidroid")

async def start_cronjob(client: Pidroid, cronjob: aiocron.Cron, cron_name: str = "Generic") -> None:
    """Creates a new cronjob task with specified parameters."""
    await client.wait_until_ready()

    try:
        logger.info(f"{cron_name} cron job task started")
        while True:
            await cronjob.next(client)
    except asyncio.CancelledError:
        with suppress(Exception):
            cronjob.stop()
            logger.info(f"{cron_name} cron job task stopped")