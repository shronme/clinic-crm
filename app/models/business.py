import uuid

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Business(Base):
    """Business model with profile, timezone, currency, branding, and policy
    management.
    """

    __tablename__ = "businesses"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    name = Column(String(255), nullable=False)

    # Business profile
    logo_url = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    website = Column(String(500), nullable=True)

    # Location & timezone
    address = Column(Text, nullable=True)
    timezone = Column(String(50), nullable=False, default="UTC")

    # Currency & financial
    currency = Column(String(10), nullable=False, default="USD")

    # Branding configuration
    branding = Column(
        JSON, nullable=True
    )  # { primary_color, secondary_color, logo_position, etc. }

    # Booking policies
    policy = Column(JSON, nullable=True)  # booking policy configuration

    # Business settings
    is_active = Column(Boolean, default=True, nullable=False)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    service_categories = relationship("ServiceCategory", back_populates="business")
    services = relationship("Service", back_populates="business")
    service_addons = relationship("ServiceAddon", back_populates="business")
    staff = relationship("Staff", back_populates="business")
