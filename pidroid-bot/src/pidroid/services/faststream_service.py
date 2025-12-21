import discord
import logging

from faststream.rabbit import RabbitBroker
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pidroid.client import Pidroid

logger = logging.getLogger("Pidroid.FastStream")


class FastStreamService:
    def __init__(self, client: "Pidroid"):
        rabbitmq_url = client.config["rabbitmq_url"] or "amqp://guest:guest@127.0.0.1:5672/"
        self.__client = client
        self.__broker = RabbitBroker(url=rabbitmq_url)
        self.__setup_handlers()

    def __setup_handlers(self) -> None:
        """Setup FastStream RPC handlers."""

        @self.__broker.subscriber("bot.query_data")
        async def handle_query_data() -> dict[str, Any]:
            """Handle query_data RPC request and return response."""
            try:
                guilds = self.__client.guilds
                data = [{"id": guild.id, "name": guild.name} for guild in guilds]
                return {"ok": True, "data": data}
            except Exception as e:
                logger.exception("query_data failed")
                return {"ok": False, "error": str(e)}

    async def start(self) -> None:
        """Start FastStream RabbitMQ service."""
        await self.__broker.start()
        logger.info("FastStream RabbitMQ service started")

    async def stop(self) -> None:
        """Stop FastStream RabbitMQ service."""
        await self.__broker.stop()
        logger.info("FastStream RabbitMQ service stopped")
