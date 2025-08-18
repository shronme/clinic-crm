from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from core.database import Base


class Service(Base):
    """Service model - placeholder for task 3."""

    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # More fields to be added in task 3
