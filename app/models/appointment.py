from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func
from app.core.database import Base

class Appointment(Base):
    """Appointment model - placeholder for task 3."""
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # More fields to be added in task 3