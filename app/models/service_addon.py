import uuid

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class ServiceAddon(Base):
    """Service add-on model with extra duration and pricing."""

    __tablename__ = "service_addons"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Add-on details
    extra_duration_minutes = Column(Integer, default=0)  # Additional time required
    price = Column(Numeric(10, 2), nullable=False)  # Add-on price

    # Add-on behavior
    is_active = Column(Boolean, default=True, nullable=False)
    is_required = Column(
        Boolean, default=False, nullable=False
    )  # If mandatory for service
    max_quantity = Column(Integer, default=1)  # Maximum units can be added

    # Display and organization
    sort_order = Column(Integer, default=0)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    business = relationship("Business", back_populates="service_addons")
    service = relationship("Service", back_populates="service_addons")

    def __repr__(self):
        return (
            f"<ServiceAddon(id={self.id}, name='{self.name}', "
            f"service_id={self.service_id}, price=${self.price})>"
        )
