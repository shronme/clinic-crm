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


class StaffService(Base):
    """Staff-service mapping model with optional overrides for pricing and duration."""

    __tablename__ = "staff_services"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)

    # Service overrides (optional)
    override_duration_minutes = Column(
        Integer, nullable=True
    )  # Override default duration
    override_price = Column(Numeric(10, 2), nullable=True)  # Override default price
    override_buffer_before_minutes = Column(
        Integer, nullable=True
    )  # Override prep time
    override_buffer_after_minutes = Column(
        Integer, nullable=True
    )  # Override cleanup time

    # Staff-specific service settings
    is_available = Column(
        Boolean, default=True, nullable=False
    )  # Can staff perform this service
    expertise_level = Column(String(50), nullable=True)  # junior, senior, expert, etc.
    notes = Column(
        Text, nullable=True
    )  # Internal notes about staff's service capability

    # Booking behavior
    requires_approval = Column(
        Boolean, default=False, nullable=False
    )  # Manual approval needed

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    staff = relationship("Staff", back_populates="staff_services")
    service = relationship("Service", back_populates="staff_services")

    @property
    def effective_duration_minutes(self):
        """Get effective duration (override or service default)."""
        return self.override_duration_minutes or self.service.duration_minutes

    @property
    def effective_price(self):
        """Get effective price (override or service default)."""
        return self.override_price or self.service.price

    @property
    def effective_buffer_before_minutes(self):
        """Get effective prep time (override or service default)."""
        return self.override_buffer_before_minutes or self.service.buffer_before_minutes

    @property
    def effective_buffer_after_minutes(self):
        """Get effective cleanup time (override or service default)."""
        return self.override_buffer_after_minutes or self.service.buffer_after_minutes

    @property
    def effective_total_duration_minutes(self):
        """Total effective time including buffers."""
        return (
            self.effective_duration_minutes
            + self.effective_buffer_before_minutes
            + self.effective_buffer_after_minutes
        )

    def __repr__(self):
        return (
            f"<StaffService(id={self.id}, staff_id={self.staff_id}, "
            f"service_id={self.service_id}, available={self.is_available})>"
        )
