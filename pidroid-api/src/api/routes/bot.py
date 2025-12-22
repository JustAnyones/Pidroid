"""Bot-related routes."""

import json

from fastapi import APIRouter, Depends, HTTPException
from faststream.rabbit import RabbitBroker
from typing import Annotated, Any

from ..dependencies import get_broker

router = APIRouter(prefix="/bot", tags=["bot"])


@router.get(
    "/query-data",
    summary="Query bot data",
    description="Query the bot for guild data via RPC",
    response_description="Guild data from the bot",
)
async def query_data(broker: Annotated[RabbitBroker, Depends(get_broker)]) -> dict[str, Any]:
    """Query the bot for guild data via FastStream RPC."""
    try:
        result = await broker.request(
            None,
            "bot.query_data",
            timeout=5.0,
        )
        print("Bot response:", result)
        return json.loads(result.body.decode("utf-8"))
    except TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Bot response timeout"
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=str(e)
        )
