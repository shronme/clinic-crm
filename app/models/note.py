from sqlalchemy import Column, Integer, String, DateTime, Text
from sqlalchemy.sql import func
from core.database import Base


class Note(Base):
    """Note model - placeholder for task 3."""

    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # More fields to be added in task 3
