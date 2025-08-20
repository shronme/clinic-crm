from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
import uuid


class Notification(Base):
    """Notification model - placeholder for task 3."""

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # More fields to be added in task 3
