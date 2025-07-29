from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pidroid.modules.moderation.models.types import PunishmentType
from pidroid.utils.db.base import Base

MAX_USERNAME_LENGTH = 255

class GuildCaseCounter(Base):
    """
    This table is used to have unique incrementing ID per guild for case.
    """

    __tablename__: str = "PunishmentCounters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    counter: Mapped[int] = mapped_column(BigInteger, server_default="1")


class ActivePunishment(Base):
    """
    Stores current active punishments that are managed by Pidroid.

    This table should never be exposed to the end user in any way.

    When a punishment is issued, it should be added to this table.
    When a punishment is revoked, it should be removed from this table.
    When a punishment expires, it should be removed from this table.
    """

    __tablename__: str = "ActivePunishments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    type: Mapped[PunishmentType] = mapped_column(Enum(PunishmentType))
    guild_id: Mapped[int] = mapped_column(BigInteger)
    user_id: Mapped[int] = mapped_column(BigInteger)
    # Date when the punishment expires. Null means the punishment is permanent.
    date_expire: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))


class ModerationCase(Base):
    """
    Stores logs of issued and revoked punishments.

    A single entry represents a single punishment that was issued, it also stores
    whether it was revoked or not.
    """

    __tablename__: str = "ModerationCases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Guild specific ID, used to differentiate between cases in different guilds, from GuildCaseCounter
    case_id: Mapped[int] = mapped_column(BigInteger)
    # Guild that the punishment was issued in
    guild_id: Mapped[int] = mapped_column(BigInteger)

    # Type of the punishment that was issued, from PunishmentType enum
    type: Mapped[PunishmentType] = mapped_column(Enum(PunishmentType))
    
    # User that was punished
    user_id: Mapped[int] = mapped_column(BigInteger)
    user_name: Mapped[str] = mapped_column(Text(MAX_USERNAME_LENGTH))

    # User that issued the punishment
    moderator_id: Mapped[int] = mapped_column(BigInteger)
    moderator_name: Mapped[str] = mapped_column(Text(MAX_USERNAME_LENGTH))

    # The reason for the punishment
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Date when the punishment was issued
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # Date when the punishment should expire. This is used for timed punishments like bans.
    # If the punishment is permanent, this will be None.
    date_expire: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))

    # Represents the ID of the managed punishment if this modlog is a managed punishment
    managed_punishment_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey('ActivePunishments.id', ondelete="SET NULL"),
        nullable=True, unique=True
    )

    # Represents the revocation data if the punishment was revoked
    revocation_data_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey('RevocationDatas.id', ondelete="SET NULL"),
        nullable=True, unique=True
    )

    active_punishment: Mapped[ActivePunishment | None] = relationship(
        foreign_keys=[managed_punishment_id]
    )
    revocation_data: Mapped[RevocationData | None] = relationship(
        foreign_keys=[revocation_data_id]
    )

    # Whether this modlog was created due to an action outside of Pidroid
    external: Mapped[bool] = mapped_column(Boolean, server_default="false")

class RevocationData(Base):
    __tablename__: str = 'RevocationDatas'
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    moderator_id: Mapped[int] = mapped_column(BigInteger)
    moderator_name: Mapped[str] = mapped_column(Text(MAX_USERNAME_LENGTH))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, default=func.now())
