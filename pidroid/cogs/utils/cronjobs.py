import aiocron # type: ignore
import asyncio

from contextlib import suppress

from pidroid.client import Pidroid

async def start_cronjob(client: Pidroid, cronjob: aiocron.Cron, cron_name: str = "Generic") -> None:
    """Creates a new cronjob task with specified parameters."""
    await client.wait_until_ready()

    try:
        client.logger.info(f"{cron_name} cron job task started")
        while True:
            await cronjob.next(client)
    except asyncio.CancelledError:
        with suppress(Exception):
            cronjob.stop()
            client.logger.info(f"{cron_name} cron job task stopped")