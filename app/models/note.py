import uuid

from sqlalchemy import Column, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.core.database import Base


class Note(Base):
    """Note model - placeholder for task 3."""

    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    content = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # More fields to be added in task 3
