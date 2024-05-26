import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class LinkedAccount(Base):
    __tablename__ = "LinkedAccounts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    forum_id: Mapped[int] = mapped_column(BigInteger)
    roles: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), server_default="{}")
    date_wage_last_redeemed: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True))