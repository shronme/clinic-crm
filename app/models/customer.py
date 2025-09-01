import enum
import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class CustomerStatus(enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLOCKED = "blocked"


class GenderType(enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"
    PREFER_NOT_TO_SAY = "prefer_not_to_say"


class Customer(Base):
    """Comprehensive Customer model for CRM functionality."""

    __tablename__ = "customers"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    business_id = Column(
        Integer, ForeignKey("businesses.id"), nullable=False, index=True
    )

    # Personal information
    first_name = Column(String(100), nullable=False, index=True)
    last_name = Column(String(100), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True, index=True)

    # Additional contact information
    alternative_phone = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    city = Column(String(100), nullable=True)
    state = Column(String(50), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(50), nullable=True, default="US")

    # Personal details
    date_of_birth = Column(Date, nullable=True)
    gender = Column(String(20), nullable=True)
    occupation = Column(String(100), nullable=True)

    # Customer preferences and notes
    preferences = Column(Text, nullable=True)  # General preferences
    allergies = Column(Text, nullable=True)  # Hair/skin allergies
    notes = Column(Text, nullable=True)  # Staff notes about customer

    # Communication preferences
    email_notifications = Column(Boolean, default=True, nullable=False)
    sms_notifications = Column(Boolean, default=True, nullable=False)
    marketing_emails = Column(Boolean, default=False, nullable=False)
    marketing_sms = Column(Boolean, default=False, nullable=False)

    # Customer status and behavior
    status = Column(
        String(20), default=CustomerStatus.ACTIVE.value, nullable=False, index=True
    )
    is_vip = Column(Boolean, default=False, nullable=False)
    referral_source = Column(String(100), nullable=True)  # How they found us
    referred_by_customer_id = Column(Integer, ForeignKey("customers.id"), nullable=True)

    # Emergency contact
    emergency_contact_name = Column(String(200), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    emergency_contact_relationship = Column(String(50), nullable=True)

    # Social media / additional contact
    instagram_handle = Column(String(100), nullable=True)
    facebook_profile = Column(String(255), nullable=True)

    # Customer lifecycle
    first_visit_date = Column(Date, nullable=True)
    last_visit_date = Column(Date, nullable=True)
    total_visits = Column(Integer, default=0, nullable=False)
    total_spent = Column(Integer, default=0, nullable=False)  # In cents

    # Customer behavior flags
    is_no_show_risk = Column(Boolean, default=False, nullable=False)
    no_show_count = Column(Integer, default=0, nullable=False)
    cancelled_appointment_count = Column(Integer, default=0, nullable=False)

    # Data source and import info
    source = Column(
        String(50), default="manual", nullable=False
    )  # manual, csv_import, online_booking, etc.
    external_id = Column(
        String(100), nullable=True, index=True
    )  # For imports/integrations

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_contacted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    business = relationship("Business")
    referred_by = relationship("Customer", remote_side=[id], backref="referrals")
    appointments = relationship("Appointment", back_populates="customer")

    @property
    def full_name(self) -> str:
        """Get customer's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_phone(self) -> str:
        """Get primary phone for display."""
        return self.phone or self.alternative_phone or ""

    @property
    def age(self) -> int:
        """Calculate customer's age from date of birth."""
        if not self.date_of_birth:
            return None

        from datetime import date

        today = date.today()
        return (
            today.year
            - self.date_of_birth.year
            - (
                (today.month, today.day)
                < (self.date_of_birth.month, self.date_of_birth.day)
            )
        )

    @property
    def lifetime_value(self) -> float:
        """Get customer's lifetime value in dollars."""
        return self.total_spent / 100.0 if self.total_spent else 0.0

    @property
    def is_new_customer(self) -> bool:
        """Check if customer is new (less than 2 visits)."""
        return self.total_visits < 2

    @property
    def risk_level(self) -> str:
        """Assess customer risk level based on behavior."""
        if self.no_show_count >= 3:
            return "high"
        elif self.no_show_count >= 1 or self.cancelled_appointment_count >= 3:
            return "medium"
        return "low"

    def update_visit_stats(self, visit_date: date = None, amount_spent: int = 0):
        """Update customer visit statistics."""
        if visit_date is None:
            visit_date = date.today()

        if self.first_visit_date is None:
            self.first_visit_date = visit_date

        self.last_visit_date = visit_date
        self.total_visits += 1
        self.total_spent += amount_spent

    def can_book_appointment(self) -> tuple[bool, str]:
        """Check if customer can book appointments based on status and behavior."""
        if self.status == CustomerStatus.BLOCKED.value:
            return False, "Customer account is blocked"

        if self.status == CustomerStatus.INACTIVE.value:
            return False, "Customer account is inactive"

        if self.no_show_count >= 5:
            return False, "Too many no-shows - contact salon directly"

        return True, ""

    def __repr__(self):
        return (
            f"<Customer(id={self.id}, name='{self.full_name}', "
            f"email='{self.email}', phone='{self.phone}', "
            f"status='{self.status}', visits={self.total_visits})>"
        )
