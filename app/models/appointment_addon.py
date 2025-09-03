import uuid

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AppointmentAddon(Base):
    """Junction table for appointment-service addon relationships."""

    __tablename__ = "appointment_addons"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )

    # Foreign keys
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=False)
    addon_id = Column(Integer, ForeignKey("service_addons.id"), nullable=False)

    # Addon details at time of booking (for historical accuracy)
    addon_name = Column(String(255), nullable=False)
    addon_price = Column(Numeric(10, 2), nullable=False)
    addon_duration_minutes = Column(Integer, nullable=False)
    quantity = Column(Integer, default=1, nullable=False)  # For future quantity support

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    appointment = relationship("Appointment", back_populates="appointment_addons")
    addon = relationship("ServiceAddon")

    def __repr__(self):
        return (
            f"<AppointmentAddon(id={self.id}, appointment_id={self.appointment_id}, "
            f"addon_id={self.addon_id}, name='{self.addon_name}', "
            f"price=${self.addon_price}, duration={self.addon_duration_minutes}min)>"
        )
