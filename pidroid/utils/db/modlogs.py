import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base


class GuildModerationLogCounter():
    """
    This table is used to have unique incrementing per guild for modlogs.
    """

    __tablename__ = "GuildModlogCounters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    counter: Mapped[int] = mapped_column(BigInteger, server_default="1")


class ActivePunishment():
    """
    Stores current active punishments that are managed by Pidroid.

    This table should never be exposed to the end user.
    """

    __tablename__ = "ActivePunishments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[str] = mapped_column(Text)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    date_expire: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True)) # date when punishment expires, null means never


class GuildModerationLog():
    """
    Stores logs of issued and revoked punishments.
    """

    __tablename__ = "GuildModlogs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    case_id: Mapped[int] = mapped_column(BigInteger) # guild specific ID

    type: Mapped[str] = mapped_column(Text)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    
    user_id: Mapped[int] = mapped_column(BigInteger)
    user_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    moderator_id: Mapped[int] = mapped_column(BigInteger)
    moderator_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    date_created: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now()) # pyright: ignore[reportAny]

    # TODO: do we need this?
    # On one hand, it's already stored in the active punishment table
    # On the other hand, information for timeouts and when they expire would not be saved as we dont manage them
    date_expire: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True)) # date when punishment expires, null means never

    # Represents the punishment that was created by this moderation log
    # TODO: setup a relationship
    managed_punishment_id: Mapped[int | None]

    # Used for invalidating warnings
    hidden: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Whether this modlog was created due to an action outside of Pidroid
    external: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # Whether the moderator responsible for the log should be displayed on the UI
    show_mod: Mapped[bool] = mapped_column(Boolean, server_default="true")