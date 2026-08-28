from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    __tablename__: str
