import datetime

from sqlalchemy import ARRAY, BigInteger, Boolean, DateTime, Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class TagTable(Base):
    __tablename__ = "Tags"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[int]] = mapped_column(ARRAY(BigInteger))
    aliases: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    locked: Mapped[bool] = mapped_column(Boolean, server_default="false")
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())
