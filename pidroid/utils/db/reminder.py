import datetime

from sqlalchemy import BigInteger, DateTime, Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class Reminder(Base):
    __tablename__ = "Reminders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    user_id: Mapped[int] = mapped_column(BigInteger)
    channel_id: Mapped[int | None] = mapped_column(BigInteger)
    message_id: Mapped[int] = mapped_column(BigInteger)
    message_url: Mapped[str] = mapped_column(Text)

    content: Mapped[str] = mapped_column(Text)
    date_remind: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())
