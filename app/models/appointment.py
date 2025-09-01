from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Numeric,
    CheckConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum
import uuid
from datetime import datetime, timedelta
from typing import Optional


class AppointmentStatus(enum.Enum):
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    RESCHEDULED = "rescheduled"


class CancellationReason(enum.Enum):
    CUSTOMER_REQUEST = "customer_request"
    STAFF_UNAVAILABLE = "staff_unavailable"
    BUSINESS_CLOSURE = "business_closure"
    EMERGENCY = "emergency"
    WEATHER = "weather"
    OTHER = "other"


class Appointment(Base):
    """Comprehensive appointment model with status transitions and policy validation."""

    __tablename__ = "appointments"

    # Core identity
    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4, index=True
    )
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False)
    
    # Appointment participants
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    staff_id = Column(Integer, ForeignKey("staff.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    
    # Scheduling details
    scheduled_datetime = Column(DateTime(timezone=True), nullable=False, index=True)
    estimated_end_datetime = Column(DateTime(timezone=True), nullable=False)
    actual_start_datetime = Column(DateTime(timezone=True), nullable=True)
    actual_end_datetime = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    
    # Status management
    status = Column(String(20), nullable=False, default=AppointmentStatus.TENTATIVE.value, index=True)
    previous_status = Column(String(20), nullable=True)
    status_changed_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Booking details
    booked_by_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    booking_source = Column(String(50), default="admin")  # admin, online, phone, walk_in
    
    # Pricing and payment
    total_price = Column(Numeric(10, 2), nullable=False)
    deposit_required = Column(Boolean, default=False)
    deposit_amount = Column(Numeric(10, 2), nullable=True)
    deposit_paid = Column(Boolean, default=False)
    deposit_paid_at = Column(DateTime(timezone=True), nullable=True)
    
    # Cancellation management
    is_cancelled = Column(Boolean, default=False, index=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_by_staff_id = Column(Integer, ForeignKey("staff.id"), nullable=True)
    cancellation_reason = Column(String(50), nullable=True)
    cancellation_notes = Column(Text, nullable=True)
    cancellation_fee = Column(Numeric(10, 2), nullable=True)
    
    # Rescheduling
    original_appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True)
    rescheduled_from_datetime = Column(DateTime(timezone=True), nullable=True)
    reschedule_count = Column(Integer, default=0)
    
    # Customer communication
    customer_notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    confirmation_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # No-show management
    is_no_show = Column(Boolean, default=False)
    no_show_fee = Column(Numeric(10, 2), nullable=True)
    
    # Slot locking for conflict prevention
    slot_locked = Column(Boolean, default=False)
    slot_locked_at = Column(DateTime(timezone=True), nullable=True)
    slot_lock_expires_at = Column(DateTime(timezone=True), nullable=True)
    locked_by_session_id = Column(String(255), nullable=True)
    
    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "estimated_end_datetime > scheduled_datetime",
            name="check_end_after_start"
        ),
        CheckConstraint(
            "duration_minutes > 0",
            name="check_positive_duration"
        ),
        CheckConstraint(
            "total_price >= 0",
            name="check_non_negative_price"
        ),
        CheckConstraint(
            "deposit_amount >= 0",
            name="check_non_negative_deposit"
        ),
        CheckConstraint(
            "reschedule_count >= 0",
            name="check_non_negative_reschedule_count"
        ),
    )
    
    # Relationships
    business = relationship("Business")
    customer = relationship("Customer")
    staff = relationship("Staff", foreign_keys=[staff_id])
    service = relationship("Service")
    booked_by_staff = relationship("Staff", foreign_keys=[booked_by_staff_id])
    cancelled_by_staff = relationship("Staff", foreign_keys=[cancelled_by_staff_id])
    original_appointment = relationship("Appointment", remote_side=[id])
    
    # Status transition methods
    def can_transition_to(self, new_status: AppointmentStatus) -> bool:
        """Check if appointment can transition to the new status."""
        current = AppointmentStatus(self.status)
        
        # Define allowed transitions
        allowed_transitions = {
            AppointmentStatus.TENTATIVE: [
                AppointmentStatus.CONFIRMED,
                AppointmentStatus.CANCELLED,
                AppointmentStatus.RESCHEDULED
            ],
            AppointmentStatus.CONFIRMED: [
                AppointmentStatus.IN_PROGRESS,
                AppointmentStatus.CANCELLED,
                AppointmentStatus.NO_SHOW,
                AppointmentStatus.RESCHEDULED
            ],
            AppointmentStatus.IN_PROGRESS: [
                AppointmentStatus.COMPLETED,
                AppointmentStatus.CANCELLED
            ],
            AppointmentStatus.COMPLETED: [],  # Final state
            AppointmentStatus.CANCELLED: [],  # Final state
            AppointmentStatus.NO_SHOW: [],  # Final state
            AppointmentStatus.RESCHEDULED: []  # Final state
        }
        
        return new_status in allowed_transitions.get(current, [])
    
    def transition_to(self, new_status: AppointmentStatus, notes: Optional[str] = None) -> bool:
        """Transition appointment to new status with validation."""
        if not self.can_transition_to(new_status):
            return False
        
        from datetime import timezone
        self.previous_status = self.status
        self.status = new_status.value
        self.status_changed_at = datetime.now(timezone.utc)
        
        # Handle status-specific logic
        if new_status == AppointmentStatus.CANCELLED:
            self.is_cancelled = True
            self.cancelled_at = datetime.now(timezone.utc)
            if notes:
                self.cancellation_notes = notes
                
        elif new_status == AppointmentStatus.NO_SHOW:
            self.is_no_show = True
            
        elif new_status == AppointmentStatus.IN_PROGRESS:
            self.actual_start_datetime = datetime.now(timezone.utc)
            
        elif new_status == AppointmentStatus.COMPLETED:
            self.actual_end_datetime = datetime.now(timezone.utc)
        
        return True
    
    def is_cancellable(self, current_time: Optional[datetime] = None) -> tuple[bool, str]:
        """Check if appointment can be cancelled based on cancellation policy."""
        if current_time is None:
            from datetime import timezone
            current_time = datetime.now(timezone.utc)
        
        # Cannot cancel completed, already cancelled, or no-show appointments
        if self.status in [AppointmentStatus.COMPLETED.value, 
                          AppointmentStatus.CANCELLED.value, 
                          AppointmentStatus.NO_SHOW.value]:
            return False, "Appointment cannot be cancelled in current status"
        
        # Check cancellation window (this would typically come from business policy)
        # For now, using a default 24-hour cancellation window
        cancellation_window = timedelta(hours=24)
        earliest_cancel_time = self.scheduled_datetime - cancellation_window
        
        if current_time > earliest_cancel_time:
            return False, "Appointment is within the cancellation window"
        
        return True, "Appointment can be cancelled"
    
    def lock_slot(self, session_id: str, lock_duration_minutes: int = 15) -> bool:
        """Lock the appointment slot to prevent conflicts during booking."""
        from datetime import timezone
        current_time = datetime.now(timezone.utc)
        if self.slot_locked and self.slot_lock_expires_at > current_time:
            return False  # Already locked by another session
        
        self.slot_locked = True
        self.slot_locked_at = current_time
        self.slot_lock_expires_at = current_time + timedelta(minutes=lock_duration_minutes)
        self.locked_by_session_id = session_id
        
        return True
    
    def unlock_slot(self, session_id: Optional[str] = None) -> bool:
        """Unlock the appointment slot."""
        if session_id and self.locked_by_session_id != session_id:
            return False  # Can only unlock if same session or force unlock
        
        self.slot_locked = False
        self.slot_locked_at = None
        self.slot_lock_expires_at = None
        self.locked_by_session_id = None
        
        return True
    
    def is_slot_locked(self) -> bool:
        """Check if slot is currently locked."""
        if not self.slot_locked:
            return False
        
        # Check if lock has expired
        from datetime import timezone
        if self.slot_lock_expires_at and self.slot_lock_expires_at <= datetime.now(timezone.utc):
            # Auto-unlock expired locks
            self.unlock_slot()
            return False
        
        return True
    
    def calculate_total_price(self, service_price: float, addon_prices: list[float] = None) -> float:
        """Calculate total appointment price including addons."""
        total = service_price
        if addon_prices:
            total += sum(addon_prices)
        return total
    
    @property
    def is_active(self) -> bool:
        """Check if appointment is in an active state."""
        return self.status not in [
            AppointmentStatus.CANCELLED.value,
            AppointmentStatus.COMPLETED.value,
            AppointmentStatus.NO_SHOW.value,
            AppointmentStatus.RESCHEDULED.value
        ]
    
    @property
    def time_until_appointment(self) -> timedelta:
        """Get time remaining until appointment."""
        from datetime import timezone
        return self.scheduled_datetime - datetime.now(timezone.utc)
    
    @property
    def is_past_due(self) -> bool:
        """Check if appointment time has passed."""
        from datetime import timezone
        return self.scheduled_datetime < datetime.now(timezone.utc)
    
    def __repr__(self):
        return (
            f"<Appointment(id={self.id}, status='{self.status}', "
            f"datetime='{self.scheduled_datetime}', "
            f"customer_id={self.customer_id}, staff_id={self.staff_id})>"
        )