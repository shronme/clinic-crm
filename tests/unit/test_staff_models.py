import pytest
from datetime import datetime, date, time, timedelta

from app.models.staff import Staff, StaffRole
from app.models.working_hours import WorkingHours, WeekDay
from app.models.time_off import TimeOff, TimeOffStatus, TimeOffType, OwnerType
from app.models.availability_override import AvailabilityOverride, OverrideType


class TestStaffModel:
    def test_staff_creation(self):
        """Test staff model creation."""
        staff = Staff(
            id=1,
            business_id=1,
            name="John Doe",
            email="john@example.com",
            phone="123-456-7890",
            role=StaffRole.STAFF,
            is_bookable=True,
            is_active=True,
        )

        assert staff.name == "John Doe"
        assert staff.email == "john@example.com"
        assert staff.role == StaffRole.STAFF
        assert staff.is_bookable is True
        assert staff.is_active is True

    def test_staff_repr(self):
        """Test staff string representation."""
        staff = Staff(
            id=1, name="Jane Smith", role=StaffRole.OWNER_ADMIN, is_bookable=False
        )

        repr_str = repr(staff)

        assert "Jane Smith" in repr_str
        assert "owner_admin" in repr_str
        assert "bookable=False" in repr_str

    def test_staff_role_enum(self):
        """Test staff role enumeration."""
        assert StaffRole.OWNER_ADMIN.value == "owner_admin"
        assert StaffRole.STAFF.value == "staff"
        assert StaffRole.FRONT_DESK.value == "front_desk"


class TestWorkingHoursModel:
    def test_working_hours_creation(self):
        """Test working hours model creation."""
        working_hours = WorkingHours(
            id=1,
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )

        assert working_hours.owner_type == OwnerType.STAFF
        assert working_hours.weekday == WeekDay.MONDAY
        assert working_hours.start_time == time(9, 0)
        assert working_hours.end_time == time(17, 0)
        assert working_hours.is_active is True

    def test_working_hours_with_break(self):
        """Test working hours with break configuration."""
        working_hours = WorkingHours(
            id=1,
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.TUESDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
            is_active=True,
        )

        assert working_hours.break_start_time == time(12, 0)
        assert working_hours.break_end_time == time(13, 0)

    def test_duration_minutes_no_break(self):
        """Test duration calculation without break."""
        working_hours = WorkingHours(
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
        )

        duration = working_hours.duration_minutes

        assert duration == 480  # 8 hours * 60 minutes

    def test_duration_minutes_with_break(self):
        """Test duration calculation with break."""
        working_hours = WorkingHours(
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
        )

        duration = working_hours.duration_minutes

        assert duration == 420  # 8 hours - 1 hour break = 7 hours * 60 minutes

    def test_is_time_available_within_hours(self):
        """Test time availability check within working hours."""
        working_hours = WorkingHours(
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )

        check_time = datetime(2024, 6, 3, 14, 30)  # 2:30 PM

        assert working_hours.is_time_available(check_time) is True

    def test_is_time_available_outside_hours(self):
        """Test time availability check outside working hours."""
        working_hours = WorkingHours(
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )

        check_time = datetime(2024, 6, 3, 19, 30)  # 7:30 PM

        assert working_hours.is_time_available(check_time) is False

    def test_is_time_available_during_break(self):
        """Test time availability check during break time."""
        working_hours = WorkingHours(
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
            is_active=True,
        )

        check_time = datetime(2024, 6, 3, 12, 30)  # 12:30 PM (break time)

        assert working_hours.is_time_available(check_time) is False

    def test_is_time_available_inactive_hours(self):
        """Test time availability check for inactive hours."""
        working_hours = WorkingHours(
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=False,  # Inactive
        )

        check_time = datetime(2024, 6, 3, 14, 30)

        assert working_hours.is_time_available(check_time) is False

    def test_working_hours_repr(self):
        """Test working hours string representation."""
        working_hours = WorkingHours(
            id=1,
            owner_type=OwnerType.STAFF,
            owner_id=1,
            weekday=WeekDay.MONDAY,
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
        )

        repr_str = repr(working_hours)

        assert "MONDAY" in repr_str
        assert "09:00:00-17:00:00" in repr_str
        assert "break=12:00:00-13:00:00" in repr_str


class TestTimeOffModel:
    def test_time_off_creation(self):
        """Test time-off model creation."""
        time_off = TimeOff(
            id=1,
            owner_type=OwnerType.STAFF,
            owner_id=1,
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            type=TimeOffType.VACATION,
            reason="Summer vacation",
            status=TimeOffStatus.PENDING,
        )

        assert time_off.owner_type == OwnerType.STAFF
        assert time_off.type == TimeOffType.VACATION
        assert time_off.reason == "Summer vacation"
        assert time_off.status == TimeOffStatus.PENDING

    def test_duration_hours(self):
        """Test time-off duration calculation in hours."""
        time_off = TimeOff(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 17, 0),  # Same day, 8 hours
        )

        duration = time_off.duration_hours

        assert duration == 8.0

    def test_duration_days(self):
        """Test time-off duration calculation in days."""
        time_off = TimeOff(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),  # 3 days
        )

        duration = time_off.duration_days

        assert duration == 3

    def test_overlaps_with_true(self):
        """Test time-off overlap detection (positive case)."""
        time_off = TimeOff(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            status=TimeOffStatus.APPROVED,
        )

        # Test overlapping period
        overlaps = time_off.overlaps_with(
            datetime(2024, 6, 2, 9, 0), datetime(2024, 6, 4, 17, 0)
        )

        assert overlaps is True

    def test_overlaps_with_false(self):
        """Test time-off overlap detection (negative case)."""
        time_off = TimeOff(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            status=TimeOffStatus.APPROVED,
        )

        # Test non-overlapping period
        overlaps = time_off.overlaps_with(
            datetime(2024, 6, 4, 9, 0), datetime(2024, 6, 6, 17, 0)
        )

        assert overlaps is False

    def test_overlaps_with_not_approved(self):
        """Test time-off overlap detection for non-approved status."""
        time_off = TimeOff(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            status=TimeOffStatus.PENDING,  # Not approved
        )

        # Even if periods overlap, should return False for non-approved
        overlaps = time_off.overlaps_with(
            datetime(2024, 6, 2, 9, 0), datetime(2024, 6, 4, 17, 0)
        )

        assert overlaps is False

    def test_is_active_at_true(self):
        """Test time-off active status check (positive case)."""
        time_off = TimeOff(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            status=TimeOffStatus.APPROVED,
        )

        check_datetime = datetime(2024, 6, 2, 14, 0)

        assert time_off.is_active_at(check_datetime) is True

    def test_is_active_at_false(self):
        """Test time-off active status check (negative case)."""
        time_off = TimeOff(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            status=TimeOffStatus.APPROVED,
        )

        check_datetime = datetime(2024, 6, 5, 14, 0)  # After time-off period

        assert time_off.is_active_at(check_datetime) is False

    def test_can_be_modified_by_owner_pending(self):
        """Test modification permission for owner with pending status."""
        time_off = TimeOff(
            owner_type=OwnerType.STAFF, owner_id=1, status=TimeOffStatus.PENDING
        )

        print(
            f"Debug: owner_type={time_off.owner_type}, owner_id={time_off.owner_id}, status={time_off.status}"
        )
        can_modify = time_off.can_be_modified_by(staff_id=1, staff_role=StaffRole.STAFF)
        print(f"Debug: can_modify result={can_modify}")

        assert can_modify is True

    def test_can_be_modified_by_admin(self):
        """Test modification permission for admin."""
        time_off = TimeOff(
            owner_type=OwnerType.STAFF, owner_id=1, status=TimeOffStatus.APPROVED
        )

        can_modify = time_off.can_be_modified_by(
            staff_id=2, staff_role=StaffRole.OWNER_ADMIN
        )

        assert can_modify is True

    def test_can_be_modified_by_other_staff(self):
        """Test modification permission denied for other staff."""
        time_off = TimeOff(
            owner_type=OwnerType.STAFF, owner_id=1, status=TimeOffStatus.PENDING
        )

        can_modify = time_off.can_be_modified_by(staff_id=2, staff_role=StaffRole.STAFF)

        assert can_modify is False

    def test_time_off_repr(self):
        """Test time-off string representation."""
        time_off = TimeOff(
            id=1,
            owner_type=OwnerType.STAFF,
            owner_id=1,
            type=TimeOffType.VACATION,
            status=TimeOffStatus.PENDING,
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
        )

        repr_str = repr(time_off)

        assert "vacation" in repr_str
        assert "pending" in repr_str
        assert "2024-06-01 - 2024-06-03" in repr_str


class TestAvailabilityOverrideModel:
    def test_availability_override_creation(self):
        """Test availability override model creation."""
        override = AvailabilityOverride(
            id=1,
            staff_id=1,
            override_type=OverrideType.UNAVAILABLE,
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            title="Doctor appointment",
            reason="Medical checkup",
            is_active=True,
            created_by_staff_id=1,
        )

        assert override.staff_id == 1
        assert override.override_type == OverrideType.UNAVAILABLE
        assert override.title == "Doctor appointment"
        assert override.reason == "Medical checkup"
        assert override.is_active is True

    def test_duration_hours(self):
        """Test override duration calculation in hours."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),  # 3 hours
        )

        duration = override.duration_hours

        assert duration == 3.0

    def test_duration_days(self):
        """Test override duration calculation in days."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),  # 3 days
        )

        duration = override.duration_days

        assert duration == 3

    def test_is_active_at_true(self):
        """Test override active status check (positive case)."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            is_active=True,
        )

        check_datetime = datetime(2024, 6, 1, 10, 30)

        assert override.is_active_at(check_datetime) is True

    def test_is_active_at_false_inactive(self):
        """Test override active status check for inactive override."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            is_active=False,  # Inactive
        )

        check_datetime = datetime(2024, 6, 1, 10, 30)

        assert override.is_active_at(check_datetime) is False

    def test_overlaps_with_true(self):
        """Test override overlap detection (positive case)."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            is_active=True,
        )

        overlaps = override.overlaps_with(
            datetime(2024, 6, 1, 10, 0), datetime(2024, 6, 1, 14, 0)
        )

        assert overlaps is True

    def test_overlaps_with_false(self):
        """Test override overlap detection (negative case)."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            is_active=True,
        )

        overlaps = override.overlaps_with(
            datetime(2024, 6, 1, 13, 0), datetime(2024, 6, 1, 15, 0)
        )

        assert overlaps is False

    def test_affects_availability_at_unavailable(self):
        """Test availability effect for unavailable override."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            override_type=OverrideType.UNAVAILABLE,
            is_active=True,
        )

        check_datetime = datetime(2024, 6, 1, 10, 0)
        effect = override.affects_availability_at(check_datetime)

        assert effect == "unavailable"

    def test_affects_availability_at_available(self):
        """Test availability effect for available override."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            override_type=OverrideType.AVAILABLE,
            is_active=True,
        )

        check_datetime = datetime(2024, 6, 1, 10, 0)
        effect = override.affects_availability_at(check_datetime)

        assert effect == "available"

    def test_affects_availability_at_outside_range(self):
        """Test availability effect outside override range."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            override_type=OverrideType.UNAVAILABLE,
            is_active=True,
        )

        check_datetime = datetime(2024, 6, 1, 15, 0)  # Outside range
        effect = override.affects_availability_at(check_datetime)

        assert effect is None

    def test_can_accept_new_bookings_at_true(self):
        """Test booking acceptance during override (allowed)."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            allow_new_bookings=True,
            is_active=True,
        )

        check_datetime = datetime(2024, 6, 1, 10, 0)
        can_book = override.can_accept_new_bookings_at(check_datetime)

        assert can_book is True

    def test_can_accept_new_bookings_at_false(self):
        """Test booking acceptance during override (not allowed)."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            allow_new_bookings=False,
            is_active=True,
        )

        check_datetime = datetime(2024, 6, 1, 10, 0)
        can_book = override.can_accept_new_bookings_at(check_datetime)

        assert can_book is False

    def test_can_accept_new_bookings_outside_override(self):
        """Test booking acceptance outside override period."""
        override = AvailabilityOverride(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            allow_new_bookings=False,
            is_active=True,
        )

        check_datetime = datetime(2024, 6, 1, 15, 0)  # Outside period
        can_book = override.can_accept_new_bookings_at(check_datetime)

        assert can_book is True  # Override doesn't apply

    def test_availability_override_repr(self):
        """Test availability override string representation."""
        override = AvailabilityOverride(
            id=1,
            staff_id=1,
            override_type=OverrideType.UNAVAILABLE,
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            is_active=True,
        )

        repr_str = repr(override)

        assert "unavailable" in repr_str
        assert "2024-06-01 - 2024-06-01" in repr_str
        assert "active=True" in repr_str
