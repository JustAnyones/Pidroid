from sqlalchemy import ARRAY, BigInteger, Boolean, Float, Text
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class GuildConfigurationTable(Base):
    __tablename__ = "GuildConfigurations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)

    prefixes: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    public_tags: Mapped[bool] = mapped_column(Boolean, server_default="false")

    jail_channel: Mapped[int | None] = mapped_column(BigInteger)
    jail_role: Mapped[int | None] = mapped_column(BigInteger)
    log_channel: Mapped[int | None] = mapped_column(BigInteger)
    punishing_moderators: Mapped[bool] = mapped_column(Boolean, server_default="false")
    appeal_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Leveling system related
    xp_system_active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    xp_per_message_min: Mapped[int] = mapped_column(BigInteger, server_default="15")
    xp_per_message_max: Mapped[int] = mapped_column(BigInteger, server_default="25")
    xp_multiplier: Mapped[float] = mapped_column(Float, server_default="1.0")
    xp_exempt_roles: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    xp_exempt_channels: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    stack_level_rewards: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Suggestion system related
    suggestion_system_active: Mapped[bool] = mapped_column(Boolean, server_default="false")
    suggestion_channel: Mapped[int | None] = mapped_column(BigInteger)
    suggestion_threads_enabled: Mapped[bool] = mapped_column(Boolean, server_default="false")
