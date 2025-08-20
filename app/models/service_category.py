from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class ServiceCategory(Base):
    """Service category model with hierarchical structure."""

    __tablename__ = "service_categories"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Hierarchical structure
    parent_id = Column(Integer, ForeignKey("service_categories.id"), nullable=True)
    sort_order = Column(Integer, default=0)

    # Display and behavior
    is_active = Column(Boolean, default=True, nullable=False)
    icon = Column(String(100), nullable=True)  # Icon class or URL
    color = Column(String(7), nullable=True)  # Hex color code

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    business = relationship("Business", back_populates="service_categories")
    parent = relationship(
        "ServiceCategory", remote_side=[id], back_populates="children"
    )
    children = relationship(
        "ServiceCategory", back_populates="parent", cascade="all, delete-orphan"
    )
    services = relationship("Service", back_populates="category")

    def __repr__(self):
        return (
            f"<ServiceCategory(id={self.id}, name='{self.name}', "
            f"business_id={self.business_id})>"
        )
