import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Text
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class PunishmentCounterTable(Base):
    __tablename__ = "PunishmentCounters"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    counter: Mapped[int] = mapped_column(BigInteger, server_default="1")

class PunishmentTable(Base):
    __tablename__ = "Punishments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True) # global ID
    case_id: Mapped[int] = mapped_column(BigInteger) # guild specific ID

    type: Mapped[str] = mapped_column(Text)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    
    user_id: Mapped[int] = mapped_column(BigInteger)
    user_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    moderator_id: Mapped[int] = mapped_column(BigInteger)
    moderator_name: Mapped[str | None] = mapped_column(Text, nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    issue_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now()) # date of issue
    expire_date: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True)) # date when punishment expires, null means never

    # This let's us now if Pidroid already dealt with this case automatically
    handled: Mapped[bool] = mapped_column(Boolean, server_default="false")
    # This hides the case from visibility
    # Usually in the case of removing invalid warnings
    visible: Mapped[bool] = mapped_column(Boolean, server_default="true")
