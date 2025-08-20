from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Enum,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class StaffRole(enum.Enum):
    OWNER_ADMIN = "owner_admin"
    STAFF = "staff"
    FRONT_DESK = "front_desk"


class Staff(Base):
    """Staff model with comprehensive profile, roles, and relationships."""

    __tablename__ = "staff"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=True)
    phone = Column(String, nullable=True)

    # Profile information
    avatar_url = Column(String, nullable=True)
    bio = Column(Text, nullable=True)

    # Role and permissions
    role = Column(Enum(StaffRole), nullable=False, default=StaffRole.STAFF)

    # Booking settings
    is_bookable = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    # Display settings
    display_order = Column(Integer, default=0, nullable=False)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    business = relationship("Business", back_populates="staff")
    staff_services = relationship(
        "StaffService", back_populates="staff", cascade="all, delete-orphan"
    )
    # Note: working_hours and time_offs are polymorphic relationships
    # They are accessed via queries using owner_type and owner_id
    # Note: appointments relationship will be added when appointment model is finalized
    availability_overrides = relationship(
        "AvailabilityOverride",
        foreign_keys="AvailabilityOverride.staff_id",
        back_populates="staff",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Staff(id={self.id}, name='{self.name}', role={self.role.value}, bookable={self.is_bookable})>"
