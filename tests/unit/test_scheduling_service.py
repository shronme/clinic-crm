import uuid
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, Mock, patch

from app.models.availability_override import AvailabilityOverride, OverrideType
from app.models.business import Business
from app.models.service import Service
from app.models.staff import Staff, StaffRole
from app.models.time_off import TimeOff, TimeOffStatus
from app.models.working_hours import OwnerType, WeekDay, WorkingHours
from app.schemas.scheduling import (
    AppointmentValidationRequest,
    AvailabilityStatus,
    BusinessHoursQuery,
    ConflictType,
    SchedulingConflict,
    StaffAvailabilityQuery,
)
from app.services.scheduling import SchedulingEngineService


class TestSchedulingEngineService:
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_db = AsyncMock()
        self.scheduling_service = SchedulingEngineService(self.mock_db)

        self.sample_business = Business(
            id=1,
            uuid=uuid.UUID("12345678-1234-1234-1234-123456789012"),
            name="Test Salon",
            timezone="America/New_York",
            policy={"min_lead_time_hours": 2, "max_advance_booking_days": 30},
        )

        self.sample_staff = Staff(
            id=1,
            uuid=uuid.UUID("12345678-1234-1234-1234-123456789013"),
            business_id=1,
            name="John Barber",
            role=StaffRole.STAFF.value,
            is_bookable=True,
            is_active=True,
        )

        self.sample_service = Service(
            id=1,
            uuid=uuid.UUID("12345678-1234-1234-1234-123456789014"),
            business_id=1,
            name="Haircut",
            duration_minutes=30,
            price=25.00,
            buffer_before_minutes=5,
            buffer_after_minutes=5,
            min_lead_time_hours=1,
            max_advance_booking_days=14,
        )

        self.sample_working_hours = WorkingHours(
            id=1,
            uuid=uuid.UUID("12345678-1234-1234-1234-123456789015"),
            owner_type=OwnerType.STAFF.value,
            owner_id=1,
            weekday=str(WeekDay.MONDAY.value),
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
            is_active=True,
        )

    async def test_get_staff_availability_basic(self):
        """Test basic staff availability query."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_staff
        self.mock_db.execute.return_value = mock_execute

        query = StaffAvailabilityQuery(
            staff_uuid=str(self.sample_staff.uuid),
            start_datetime=datetime(2024, 1, 15, 9, 0),  # Monday
            end_datetime=datetime(2024, 1, 15, 17, 0),
            slot_duration_minutes=30,
        )

        with patch.object(
            self.scheduling_service, "_check_slot_availability"
        ) as mock_check:
            mock_check.return_value = (AvailabilityStatus.AVAILABLE, [])

            slots = await self.scheduling_service.get_staff_availability(query)

            assert len(slots) == 16  # 8 hours * 2 (30-min slots)
            assert all(slot.status == AvailabilityStatus.AVAILABLE for slot in slots)
            assert all(slot.staff_uuid == str(self.sample_staff.uuid) for slot in slots)

    async def test_get_staff_availability_with_service(self):
        """Test staff availability query with specific service."""
        mock_exec_result = Mock()
        mock_exec_result.scalar_one_or_none.side_effect = [
            self.sample_staff,
            self.sample_service,
        ]
        self.mock_db.execute.return_value = mock_exec_result

        query = StaffAvailabilityQuery(
            staff_uuid=str(self.sample_staff.uuid),
            start_datetime=datetime(2024, 1, 15, 9, 0),
            end_datetime=datetime(2024, 1, 15, 17, 0),
            service_uuid=str(self.sample_service.uuid),
            slot_duration_minutes=40,  # Service duration
        )

        with patch.object(
            self.scheduling_service, "_check_slot_availability"
        ) as mock_check:
            mock_check.return_value = (AvailabilityStatus.AVAILABLE, [])

            slots = await self.scheduling_service.get_staff_availability(query)

            assert len(slots) == 12  # 8 hours * 1.5 (40-min slots)
            assert all(
                slot.service_uuid == str(self.sample_service.uuid) for slot in slots
            )

    async def test_get_staff_availability_staff_not_found(self):
        """Test availability query when staff is not found."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_execute

        query = StaffAvailabilityQuery(
            staff_uuid="nonexistent-staff",
            start_datetime=datetime(2024, 1, 15, 9, 0),
            end_datetime=datetime(2024, 1, 15, 17, 0),
            slot_duration_minutes=30,
        )

        slots = await self.scheduling_service.get_staff_availability(query)
        assert len(slots) == 0

    async def test_validate_appointment_valid(self):
        """Test valid appointment validation."""
        mock_exec_result = Mock()
        mock_exec_result.scalar_one_or_none.side_effect = [
            self.sample_staff,
            self.sample_service,
        ]
        self.mock_db.execute.return_value = mock_exec_result

        request = AppointmentValidationRequest(
            staff_uuid=str(self.sample_staff.uuid),
            service_uuid=str(self.sample_service.uuid),
            requested_datetime=datetime(2024, 1, 15, 10, 0),
            addon_uuids=[],
        )

        with patch.object(
            self.scheduling_service, "_validate_scheduling_constraints"
        ) as mock_validate:
            mock_validate.return_value = []
            with patch.object(
                self.scheduling_service, "_calculate_addon_duration"
            ) as mock_addon:
                mock_addon.return_value = 0

                response = await self.scheduling_service.validate_appointment(request)

                assert response.is_valid is True
                assert len(response.conflicts) == 0
                assert (
                    response.total_duration_minutes == 40
                )  # 30 + 5 + 5 (service + buffers)

    async def test_validate_appointment_with_conflicts(self):
        """Test appointment validation with conflicts."""
        mock_exec_result = Mock()
        mock_exec_result.scalar_one_or_none.side_effect = [
            self.sample_staff,
            self.sample_service,
        ]
        self.mock_db.execute.return_value = mock_exec_result

        request = AppointmentValidationRequest(
            staff_uuid=str(self.sample_staff.uuid),
            service_uuid=str(self.sample_service.uuid),
            requested_datetime=datetime(2024, 1, 15, 10, 0),
            addon_uuids=[],
        )

        conflicts = [
            SchedulingConflict(
                conflict_type=ConflictType.EXISTING_APPOINTMENT,
                message="Staff has existing appointment",
                start_datetime=request.requested_datetime,
                end_datetime=request.requested_datetime + timedelta(minutes=40),
            )
        ]

        with patch.object(
            self.scheduling_service, "_validate_scheduling_constraints"
        ) as mock_validate:
            mock_validate.return_value = conflicts
            with patch.object(
                self.scheduling_service, "_calculate_addon_duration"
            ) as mock_addon:
                mock_addon.return_value = 0
                with patch.object(
                    self.scheduling_service, "_find_alternative_slots"
                ) as mock_alternatives:
                    mock_alternatives.return_value = []

                    response = await self.scheduling_service.validate_appointment(
                        request
                    )

                    assert response.is_valid is False
                    assert len(response.conflicts) == 1
                    assert (
                        response.conflicts[0].conflict_type
                        == ConflictType.EXISTING_APPOINTMENT
                    )

    async def test_validate_appointment_staff_not_found(self):
        """Test appointment validation when staff is not found."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_execute

        request = AppointmentValidationRequest(
            staff_uuid="nonexistent-staff",
            service_uuid=str(self.sample_service.uuid),
            requested_datetime=datetime(2024, 1, 15, 10, 0),
        )

        response = await self.scheduling_service.validate_appointment(request)

        assert response.is_valid is False
        assert len(response.conflicts) == 1
        assert response.conflicts[0].conflict_type == ConflictType.STAFF_UNAVAILABLE

    async def test_check_slot_availability_within_hours(self):
        """Test slot availability check within working hours."""
        start_time = datetime(2024, 1, 15, 10, 0)  # Monday 10 AM
        end_time = datetime(2024, 1, 15, 10, 30)  # Monday 10:30 AM

        with patch.object(
            self.scheduling_service, "_is_within_business_hours"
        ) as mock_business_hours:
            mock_business_hours.return_value = True
            with patch.object(
                self.scheduling_service, "_is_within_staff_working_hours"
            ) as mock_staff_hours:
                mock_staff_hours.return_value = True
                with patch.object(
                    self.scheduling_service, "_has_time_off_conflict"
                ) as mock_time_off:
                    mock_time_off.return_value = False
                    with patch.object(
                        self.scheduling_service, "_check_availability_overrides"
                    ) as mock_overrides:
                        mock_overrides.return_value = None
                        with patch.object(
                            self.scheduling_service, "_has_appointment_conflict"
                        ) as mock_appointments:
                            mock_appointments.return_value = False
                            with patch.object(
                                self.scheduling_service, "_check_lead_time_policy"
                            ) as mock_lead:
                                mock_lead.return_value = True
                                with patch.object(
                                    self.scheduling_service,
                                    "_check_advance_booking_policy",
                                ) as mock_advance:
                                    mock_advance.return_value = True

                                    (
                                        status,
                                        conflicts,
                                    ) = await self.scheduling_service._check_slot_availability(
                                        self.sample_staff,
                                        start_time,
                                        end_time,
                                        self.sample_service,
                                    )

                                    assert status == AvailabilityStatus.AVAILABLE
                                    assert len(conflicts) == 0

    async def test_check_slot_availability_outside_hours(self):
        """Test slot availability check outside working hours."""
        start_time = datetime(2024, 1, 15, 20, 0)  # Monday 8 PM (outside hours)
        end_time = datetime(2024, 1, 15, 20, 30)

        with patch.object(
            self.scheduling_service, "_is_within_business_hours"
        ) as mock_business_hours:
            mock_business_hours.return_value = False
            with patch.object(
                self.scheduling_service, "_is_within_staff_working_hours"
            ) as mock_staff_hours:
                mock_staff_hours.return_value = False
                with patch.object(
                    self.scheduling_service, "_has_time_off_conflict"
                ) as mock_time_off:
                    mock_time_off.return_value = False
                    with patch.object(
                        self.scheduling_service, "_check_availability_overrides"
                    ) as mock_overrides:
                        mock_overrides.return_value = None
                        with patch.object(
                            self.scheduling_service, "_has_appointment_conflict"
                        ) as mock_appointments:
                            mock_appointments.return_value = False

                            (
                                status,
                                conflicts,
                            ) = await self.scheduling_service._check_slot_availability(
                                self.sample_staff, start_time, end_time
                            )

                            assert status == AvailabilityStatus.UNAVAILABLE
                            assert ConflictType.OUTSIDE_WORKING_HOURS in conflicts

    async def test_is_within_business_hours(self):
        """Test business hours validation."""
        business_id = 1
        test_time = datetime(2024, 1, 15, 10, 0)  # Monday 10 AM

        business_hours = WorkingHours(
            owner_type=OwnerType.BUSINESS.value,
            owner_id=business_id,
            weekday=str(WeekDay.MONDAY.value),
            start_time=time(9, 0),
            end_time=time(17, 0),
            is_active=True,
        )
        business_hours.is_time_available = Mock(return_value=True)

        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = business_hours
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._is_within_business_hours(
            business_id, test_time, test_time + timedelta(minutes=30)
        )

        assert result is True

    async def test_is_within_business_hours_no_hours(self):
        """Test business hours validation when no hours are defined."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._is_within_business_hours(
            1, datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 10, 30)
        )

        assert result is False

    async def test_is_within_staff_working_hours(self):
        """Test staff working hours validation."""
        staff_id = 1
        test_time = datetime(2024, 1, 15, 10, 0)  # Monday 10 AM

        self.sample_working_hours.is_time_available = Mock(return_value=True)
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_working_hours
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._is_within_staff_working_hours(
            staff_id, test_time, test_time + timedelta(minutes=30)
        )

        assert result is True

    async def test_has_time_off_conflict(self):
        """Test time off conflict detection."""
        staff_id = 1
        test_start = datetime(2024, 1, 15, 10, 0)
        test_end = datetime(2024, 1, 15, 11, 0)

        time_off = TimeOff(
            owner_type=OwnerType.STAFF.value,
            owner_id=staff_id,
            status=TimeOffStatus.APPROVED,
            start_datetime=datetime(2024, 1, 15, 9, 0),
            end_datetime=datetime(2024, 1, 15, 12, 0),
        )

        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = time_off
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._has_time_off_conflict(
            staff_id, test_start, test_end
        )

        assert result is True

    async def test_has_no_time_off_conflict(self):
        """Test no time off conflict."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._has_time_off_conflict(
            1, datetime(2024, 1, 15, 10, 0), datetime(2024, 1, 15, 11, 0)
        )

        assert result is False

    async def test_check_availability_overrides(self):
        """Test availability overrides check."""
        staff_id = 1
        test_time = datetime(2024, 1, 15, 10, 0)

        override = AvailabilityOverride(
            staff_id=staff_id,
            override_type=OverrideType.UNAVAILABLE,
            start_datetime=datetime(2024, 1, 15, 9, 0),
            end_datetime=datetime(2024, 1, 15, 12, 0),
            is_active=True,
        )
        override.affects_availability_at = Mock(return_value="unavailable")

        mock_execute = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = [override]
        mock_execute.scalars.return_value = mock_scalars
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._check_availability_overrides(
            staff_id, test_time, test_time + timedelta(minutes=30)
        )

        assert result == "unavailable"

    async def test_check_lead_time_policy_valid(self):
        """Test lead time policy validation - valid."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_business
        self.mock_db.execute.return_value = mock_execute

        # Request 3 hours in advance (meets 1-hour minimum)
        with patch("app.services.scheduling.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 7, 0)
            future_time = datetime(2024, 1, 15, 10, 0)

            result = await self.scheduling_service._check_lead_time_policy(
                1, self.sample_service, future_time
            )

            assert result is True

    async def test_check_lead_time_policy_invalid(self):
        """Test lead time policy validation - invalid."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_business
        self.mock_db.execute.return_value = mock_execute

        # Request 30 minutes in advance (violates 1-hour minimum)
        with patch("app.services.scheduling.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 15, 9, 30)
            future_time = datetime(2024, 1, 15, 10, 0)

            result = await self.scheduling_service._check_lead_time_policy(
                1, self.sample_service, future_time
            )

            assert result is False

    async def test_check_advance_booking_policy_valid(self):
        """Test advance booking policy validation - valid."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_business
        self.mock_db.execute.return_value = mock_execute

        # Request 7 days in advance (within 14-day limit)
        with patch("app.services.scheduling.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 8, 10, 0)
            future_time = datetime(2024, 1, 15, 10, 0)

            result = await self.scheduling_service._check_advance_booking_policy(
                1, self.sample_service, future_time
            )

            assert result is True

    async def test_check_advance_booking_policy_invalid(self):
        """Test advance booking policy validation - invalid."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_business
        self.mock_db.execute.return_value = mock_execute

        # Request 20 days in advance (exceeds 14-day limit)
        with patch("app.services.scheduling.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2024, 1, 1, 10, 0)
            future_time = datetime(2024, 1, 21, 10, 0)

            result = await self.scheduling_service._check_advance_booking_policy(
                1, self.sample_service, future_time
            )

            assert result is False

    async def test_get_business_hours(self):
        """Test business hours retrieval."""
        working_hours = WorkingHours(
            owner_type=OwnerType.BUSINESS.value,
            owner_id=1,
            weekday=str(WeekDay.MONDAY.value),
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
            is_active=True,
        )
        # Patch duration_minutes as a method for the duration of this test
        with patch.object(WorkingHours, "duration_minutes", return_value=480):
            mock_execute = Mock()
            mock_execute.scalar_one_or_none.side_effect = [
                self.sample_business,
                working_hours,
            ]
            self.mock_db.execute.return_value = mock_execute

            query = BusinessHoursQuery(
                business_uuid=str(self.sample_business.uuid),
                date=datetime(2024, 1, 15),  # Monday
                include_breaks=True,
            )

            result = await self.scheduling_service.get_business_hours(query)

            assert result["is_open"] is True
            assert result["weekday"] == "MONDAY"
            assert result["hours"]["start_time"] == "09:00:00"
            assert result["hours"]["end_time"] == "17:00:00"
            assert result["hours"]["break"]["start_time"] == "12:00:00"
            assert result["hours"]["break"]["end_time"] == "13:00:00"

    async def test_get_business_hours_closed(self):
        """Test business hours retrieval when closed."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.side_effect = [self.sample_business, None]
        self.mock_db.execute.return_value = mock_execute

        query = BusinessHoursQuery(
            business_uuid=str(self.sample_business.uuid),
            date=datetime(2024, 1, 14),  # Sunday (assuming closed)
        )

        result = await self.scheduling_service.get_business_hours(query)

        assert result["is_open"] is False
        assert result["weekday"] == "SUNDAY"
        assert result["hours"] is None

    def test_calculate_addon_duration_empty(self):
        """Test addon duration calculation with empty list."""
        result = self.scheduling_service._calculate_addon_duration([])
        assert result == 0

    async def test_get_staff_by_uuid(self):
        """Test staff retrieval by UUID."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_staff
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._get_staff_by_uuid(
            str(self.sample_staff.uuid)
        )

        assert result == self.sample_staff

    async def test_get_staff_by_uuid_not_found(self):
        """Test staff retrieval by UUID when not found."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._get_staff_by_uuid("nonexistent-uuid")

        assert result is None

    async def test_get_service_by_uuid(self):
        """Test service retrieval by UUID."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.sample_service
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._get_service_by_uuid(
            str(self.sample_service.uuid)
        )

        assert result == self.sample_service

    async def test_get_service_by_uuid_not_found(self):
        """Test service retrieval by UUID when not found."""
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        self.mock_db.execute.return_value = mock_execute

        result = await self.scheduling_service._get_service_by_uuid("nonexistent-uuid")

        assert result is None
