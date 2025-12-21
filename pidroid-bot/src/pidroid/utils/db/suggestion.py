import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime, Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class SuggestionTable(Base):
    __tablename__ = "Suggestions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    author_id: Mapped[int] = mapped_column(BigInteger)
    message_id: Mapped[int | None] = mapped_column(BigInteger)
    suggestion: Mapped[str] = mapped_column(Text)
    date_submitted: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    attachments: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
