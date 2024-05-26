import datetime

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class RoleChangeQueue(Base):
    __tablename__ = "RoleChangeQueue"
    
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    action: Mapped[int] = mapped_column(Integer) # RoleAction
    status: Mapped[int] = mapped_column(Integer) # RoleQueueState
    guild_id: Mapped[int]= mapped_column(BigInteger)
    member_id: Mapped[int] = mapped_column(BigInteger)
    role_id: Mapped[int] = mapped_column(BigInteger)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=func.now()) # pyright: ignore[reportAny]