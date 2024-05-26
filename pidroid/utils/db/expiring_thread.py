import datetime

from sqlalchemy import BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class ExpiringThread(Base):
    __tablename__ = "ExpiringThreads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    thread_id: Mapped[int] = mapped_column(BigInteger)
    expiration_date: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))