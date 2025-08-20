from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Numeric,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class Service(Base):
    """Service model with duration, pricing, and buffer management."""

    __tablename__ = "services"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("service_categories.id"), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Service details
    duration_minutes = Column(Integer, nullable=False)  # Service duration
    price = Column(Numeric(10, 2), nullable=False)  # Base price

    # Buffer management
    buffer_before_minutes = Column(Integer, default=0)  # Setup/prep time
    buffer_after_minutes = Column(Integer, default=0)  # Cleanup time

    # Service behavior
    is_active = Column(Boolean, default=True, nullable=False)
    requires_deposit = Column(Boolean, default=False, nullable=False)
    deposit_amount = Column(Numeric(10, 2), nullable=True)
    max_advance_booking_days = Column(
        Integer, nullable=True
    )  # Override business default
    min_lead_time_hours = Column(Integer, nullable=True)  # Override business default

    # Display and organization
    sort_order = Column(Integer, default=0)
    image_url = Column(String(500), nullable=True)
    color = Column(String(7), nullable=True)  # Hex color code

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    business = relationship("Business", back_populates="services")
    category = relationship("ServiceCategory", back_populates="services")
    staff_services = relationship("StaffService", back_populates="service")
    service_addons = relationship("ServiceAddon", back_populates="service")

    @property
    def total_duration_minutes(self):
        """Total time including buffers."""
        return (
            self.duration_minutes
            + self.buffer_before_minutes
            + self.buffer_after_minutes
        )

    def __repr__(self):
        return (
            f"<Service(id={self.id}, name='{self.name}', "
            f"duration={self.duration_minutes}min, price=${self.price})>"
        )
