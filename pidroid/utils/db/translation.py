from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from pidroid.utils.db.base import Base

class Translation(Base):
    __tablename__ = "Translations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    original_content: Mapped[str] = mapped_column(Text)
    detected_language: Mapped[str] = mapped_column(Text)
    translated_string: Mapped[str] = mapped_column(Text)
