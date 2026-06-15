from pydantic import BaseModel


class ScamContext(BaseModel):
    """Context information for scam detection requests and confirmations."""

    message_id: int
    "The message ID associated with the scam detection request."
    guild_id: int
    "The guild ID where the message was posted."
    channel_id: int
    "The channel ID where the message was posted."
    user_id: int
    "The user ID of the message author."

class ScamDetectionRequest(BaseModel):
    """Request model for scam detection."""

    context: ScamContext
    "The context information for the scam detection request."

    attachment_url: str
    "The URL of the attachment to be analysed for scam detection."

class ScamDetectionConfirmation(BaseModel):
    """Model for scam detection confirmation."""

    context: ScamContext
    "The context information for the scam detection confirmation."
