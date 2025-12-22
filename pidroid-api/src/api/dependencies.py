"""Dependency injection for the API."""

from faststream.rabbit import RabbitBroker

from .config import settings

# Initialize RabbitMQ broker
broker = RabbitBroker(url=settings.RABBITMQ_URL)


async def get_broker() -> RabbitBroker:
    """Get the RabbitMQ broker instance."""
    return broker
