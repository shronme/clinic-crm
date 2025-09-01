from datetime import datetime, timedelta
from unittest.mock import patch

from app.models.appointment import Appointment, AppointmentStatus


class TestAppointmentStatusTransitions:
    """Test appointment status transition logic."""

    def test_can_transition_to_valid_transitions(self):
        """Test valid status transitions are allowed."""
        appointment = Appointment(status=AppointmentStatus.TENTATIVE.value)

        # From TENTATIVE
        assert appointment.can_transition_to(AppointmentStatus.CONFIRMED)
        assert appointment.can_transition_to(AppointmentStatus.CANCELLED)
        assert appointment.can_transition_to(AppointmentStatus.RESCHEDULED)

        appointment.status = AppointmentStatus.CONFIRMED.value
        # From CONFIRMED
        assert appointment.can_transition_to(AppointmentStatus.IN_PROGRESS)
        assert appointment.can_transition_to(AppointmentStatus.CANCELLED)
        assert appointment.can_transition_to(AppointmentStatus.NO_SHOW)
        assert appointment.can_transition_to(AppointmentStatus.RESCHEDULED)

        appointment.status = AppointmentStatus.IN_PROGRESS.value
        # From IN_PROGRESS
        assert appointment.can_transition_to(AppointmentStatus.COMPLETED)
        assert appointment.can_transition_to(AppointmentStatus.CANCELLED)

    def test_can_transition_to_invalid_transitions(self):
        """Test invalid status transitions are rejected."""
        appointment = Appointment(status=AppointmentStatus.COMPLETED.value)

        # From COMPLETED (final state)
        assert not appointment.can_transition_to(AppointmentStatus.TENTATIVE)
        assert not appointment.can_transition_to(AppointmentStatus.CONFIRMED)
        assert not appointment.can_transition_to(AppointmentStatus.IN_PROGRESS)
        assert not appointment.can_transition_to(AppointmentStatus.CANCELLED)

        appointment.status = AppointmentStatus.CANCELLED.value
        # From CANCELLED (final state)
        assert not appointment.can_transition_to(AppointmentStatus.CONFIRMED)
        assert not appointment.can_transition_to(AppointmentStatus.COMPLETED)

    @patch("app.models.appointment.datetime")
    def test_transition_to_success(self, mock_datetime):
        """Test successful status transition with side effects."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(status=AppointmentStatus.TENTATIVE.value)

        success = appointment.transition_to(AppointmentStatus.CONFIRMED)

        assert success
        assert appointment.status == AppointmentStatus.CONFIRMED.value
        assert appointment.previous_status == AppointmentStatus.TENTATIVE.value
        assert appointment.status_changed_at == mock_now

    @patch("app.models.appointment.datetime")
    def test_transition_to_cancelled_side_effects(self, mock_datetime):
        """Test cancellation side effects are applied."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(status=AppointmentStatus.CONFIRMED.value)

        success = appointment.transition_to(
            AppointmentStatus.CANCELLED, notes="Customer requested"
        )

        assert success
        assert appointment.status == AppointmentStatus.CANCELLED.value
        assert appointment.is_cancelled
        assert appointment.cancelled_at == mock_now
        assert appointment.cancellation_notes == "Customer requested"

    @patch("app.models.appointment.datetime")
    def test_transition_to_no_show_side_effects(self, mock_datetime):
        """Test no-show side effects are applied."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(status=AppointmentStatus.CONFIRMED.value)

        success = appointment.transition_to(AppointmentStatus.NO_SHOW)

        assert success
        assert appointment.status == AppointmentStatus.NO_SHOW.value
        assert appointment.is_no_show

    @patch("app.models.appointment.datetime")
    def test_transition_to_in_progress_side_effects(self, mock_datetime):
        """Test in-progress side effects are applied."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(status=AppointmentStatus.CONFIRMED.value)

        success = appointment.transition_to(AppointmentStatus.IN_PROGRESS)

        assert success
        assert appointment.status == AppointmentStatus.IN_PROGRESS.value
        assert appointment.actual_start_datetime == mock_now

    @patch("app.models.appointment.datetime")
    def test_transition_to_completed_side_effects(self, mock_datetime):
        """Test completion side effects are applied."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(status=AppointmentStatus.IN_PROGRESS.value)

        success = appointment.transition_to(AppointmentStatus.COMPLETED)

        assert success
        assert appointment.status == AppointmentStatus.COMPLETED.value
        assert appointment.actual_end_datetime == mock_now

    def test_transition_to_invalid_transition(self):
        """Test invalid transition returns False."""
        appointment = Appointment(status=AppointmentStatus.COMPLETED.value)

        success = appointment.transition_to(AppointmentStatus.CONFIRMED)

        assert not success
        assert appointment.status == AppointmentStatus.COMPLETED.value
        assert appointment.previous_status is None


class TestAppointmentCancellationPolicy:
    """Test appointment cancellation policy logic."""

    @patch("app.models.appointment.datetime")
    def test_is_cancellable_outside_window(self, mock_datetime):
        """Test appointment can be cancelled outside cancellation window."""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        appointment_time = datetime(2024, 1, 16, 14, 0, 0)  # 28 hours later
        mock_datetime.now.return_value = current_time

        appointment = Appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_datetime=appointment_time,
        )

        can_cancel, reason = appointment.is_cancellable(current_time)

        assert can_cancel
        assert reason == "Appointment can be cancelled"

    @patch("app.models.appointment.datetime")
    def test_is_cancellable_within_window(self, mock_datetime):
        """Test appointment cannot be cancelled within cancellation window."""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        appointment_time = datetime(2024, 1, 15, 12, 0, 0)  # 2 hours later
        mock_datetime.now.return_value = current_time

        appointment = Appointment(
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_datetime=appointment_time,
        )

        can_cancel, reason = appointment.is_cancellable(current_time)

        assert not can_cancel
        assert "within the cancellation window" in reason

    def test_is_cancellable_completed_appointment(self):
        """Test completed appointment cannot be cancelled."""
        appointment = Appointment(status=AppointmentStatus.COMPLETED.value)

        can_cancel, reason = appointment.is_cancellable()

        assert not can_cancel
        assert "cannot be cancelled in current status" in reason

    def test_is_cancellable_already_cancelled(self):
        """Test already cancelled appointment cannot be cancelled."""
        appointment = Appointment(status=AppointmentStatus.CANCELLED.value)

        can_cancel, reason = appointment.is_cancellable()

        assert not can_cancel
        assert "cannot be cancelled in current status" in reason


class TestAppointmentSlotLocking:
    """Test appointment slot locking functionality."""

    @patch("app.models.appointment.datetime")
    def test_lock_slot_success(self, mock_datetime):
        """Test successful slot locking."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment()
        session_id = "test_session_123"

        success = appointment.lock_slot(session_id, 20)

        assert success
        assert appointment.slot_locked
        assert appointment.slot_locked_at == mock_now
        assert appointment.slot_lock_expires_at == mock_now + timedelta(minutes=20)
        assert appointment.locked_by_session_id == session_id

    @patch("app.models.appointment.datetime")
    def test_lock_slot_already_locked_by_other_session(self, mock_datetime):
        """Test cannot lock slot already locked by another session."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        future_time = mock_now + timedelta(minutes=10)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(
            slot_locked=True,
            slot_lock_expires_at=future_time,
            locked_by_session_id="other_session",
        )

        success = appointment.lock_slot("test_session_123", 15)

        assert not success
        assert appointment.locked_by_session_id == "other_session"

    @patch("app.models.appointment.datetime")
    def test_lock_slot_expired_lock_override(self, mock_datetime):
        """Test can lock slot with expired lock."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        past_time = mock_now - timedelta(minutes=10)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(
            slot_locked=True,
            slot_lock_expires_at=past_time,
            locked_by_session_id="expired_session",
        )

        success = appointment.lock_slot("test_session_123", 15)

        assert success
        assert appointment.locked_by_session_id == "test_session_123"

    def test_unlock_slot_success(self):
        """Test successful slot unlocking."""
        session_id = "test_session_123"
        appointment = Appointment(slot_locked=True, locked_by_session_id=session_id)

        success = appointment.unlock_slot(session_id)

        assert success
        assert not appointment.slot_locked
        assert appointment.slot_locked_at is None
        assert appointment.slot_lock_expires_at is None
        assert appointment.locked_by_session_id is None

    def test_unlock_slot_different_session(self):
        """Test cannot unlock slot locked by different session."""
        appointment = Appointment(
            slot_locked=True, locked_by_session_id="other_session"
        )

        success = appointment.unlock_slot("test_session_123")

        assert not success
        assert appointment.slot_locked
        assert appointment.locked_by_session_id == "other_session"

    def test_unlock_slot_force_unlock(self):
        """Test force unlock without session ID."""
        appointment = Appointment(slot_locked=True, locked_by_session_id="any_session")

        success = appointment.unlock_slot()

        assert success
        assert not appointment.slot_locked

    @patch("app.models.appointment.datetime")
    def test_is_slot_locked_true(self, mock_datetime):
        """Test slot is locked when lock is active."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        future_time = mock_now + timedelta(minutes=10)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(slot_locked=True, slot_lock_expires_at=future_time)

        assert appointment.is_slot_locked()

    @patch("app.models.appointment.datetime")
    def test_is_slot_locked_auto_unlock_expired(self, mock_datetime):
        """Test expired lock is automatically unlocked."""
        mock_now = datetime(2024, 1, 15, 10, 30, 0)
        past_time = mock_now - timedelta(minutes=10)
        mock_datetime.now.return_value = mock_now

        appointment = Appointment(slot_locked=True, slot_lock_expires_at=past_time)

        # Should auto-unlock and return False
        assert not appointment.is_slot_locked()
        assert not appointment.slot_locked

    def test_is_slot_locked_false(self):
        """Test slot is not locked when lock is inactive."""
        appointment = Appointment(slot_locked=False)

        assert not appointment.is_slot_locked()


class TestAppointmentBusinessLogic:
    """Test appointment business logic methods."""

    def test_calculate_total_price_service_only(self):
        """Test price calculation with service only."""
        appointment = Appointment()

        total = appointment.calculate_total_price(50.00)

        assert total == 50.00

    def test_calculate_total_price_with_addons(self):
        """Test price calculation with addons."""
        appointment = Appointment()

        total = appointment.calculate_total_price(50.00, [15.00, 10.00, 5.00])

        assert total == 80.00

    def test_calculate_total_price_no_addons(self):
        """Test price calculation with empty addons list."""
        appointment = Appointment()

        total = appointment.calculate_total_price(50.00, [])

        assert total == 50.00


class TestAppointmentProperties:
    """Test appointment computed properties."""

    def test_is_active_true(self):
        """Test appointment is active for non-final statuses."""
        active_statuses = [
            AppointmentStatus.TENTATIVE,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.IN_PROGRESS,
        ]

        for status in active_statuses:
            appointment = Appointment(status=status.value)
            assert appointment.is_active

    def test_is_active_false(self):
        """Test appointment is not active for final statuses."""
        inactive_statuses = [
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
            AppointmentStatus.RESCHEDULED,
        ]

        for status in inactive_statuses:
            appointment = Appointment(status=status.value)
            assert not appointment.is_active

    @patch("app.models.appointment.datetime")
    def test_time_until_appointment(self, mock_datetime):
        """Test time until appointment calculation."""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        appointment_time = datetime(2024, 1, 15, 14, 0, 0)
        mock_datetime.now.return_value = current_time

        appointment = Appointment(scheduled_datetime=appointment_time)

        time_until = appointment.time_until_appointment

        assert time_until == timedelta(hours=4)

    @patch("app.models.appointment.datetime")
    def test_is_past_due_false(self, mock_datetime):
        """Test appointment is not past due when in future."""
        current_time = datetime(2024, 1, 15, 10, 0, 0)
        appointment_time = datetime(2024, 1, 15, 14, 0, 0)
        mock_datetime.now.return_value = current_time

        appointment = Appointment(scheduled_datetime=appointment_time)

        assert not appointment.is_past_due

    @patch("app.models.appointment.datetime")
    def test_is_past_due_true(self, mock_datetime):
        """Test appointment is past due when in past."""
        current_time = datetime(2024, 1, 15, 14, 0, 0)
        appointment_time = datetime(2024, 1, 15, 10, 0, 0)
        mock_datetime.now.return_value = current_time

        appointment = Appointment(scheduled_datetime=appointment_time)

        assert appointment.is_past_due

    def test_repr(self):
        """Test appointment string representation."""
        appointment = Appointment(
            id=123,
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_datetime=datetime(2024, 1, 15, 14, 0, 0),
            customer_id=456,
            staff_id=789,
        )

        repr_str = repr(appointment)

        assert "Appointment(id=123" in repr_str
        assert "status='confirmed'" in repr_str
        assert "customer_id=456" in repr_str
        assert "staff_id=789" in repr_str
