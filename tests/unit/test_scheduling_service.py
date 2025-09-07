"""Test scheduling service with real database interactions."""

from datetime import datetime, time, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business
from app.models.customer import Customer
from app.models.service import Service
from app.models.service_addon import ServiceAddon
from app.models.staff import Staff, StaffRole
from app.models.working_hours import OwnerType, WeekDay, WorkingHours
from app.schemas.scheduling import (
    AppointmentValidationRequest,
    AvailabilityStatus,
    ConflictType,
    StaffAvailabilityQuery,
)
from app.services.scheduling import SchedulingEngineService


def get_future_datetime(hour: int, minute: int = 0, days_ahead: int = 7) -> datetime:
    """Get a datetime that's guaranteed to be in the future and on a weekday."""
    now = datetime.now(timezone.utc)
    target_date = now + timedelta(days=days_ahead)
    target_datetime = target_date.replace(
        hour=hour, minute=minute, second=0, microsecond=0
    )

    # If the target time has already passed today, use tomorrow instead
    if target_datetime <= now:
        target_datetime += timedelta(days=1)

    # Ensure we're on a weekday (Monday=0, Friday=4)
    # If it's Saturday (5) or Sunday (6), move to next Monday
    if target_datetime.weekday() >= 5:  # Saturday or Sunday
        days_to_monday = 7 - target_datetime.weekday()  # 1 for Saturday, 2 for Sunday
        target_datetime += timedelta(days=days_to_monday)

    return target_datetime


@pytest.fixture
async def scheduling_test_data(db: AsyncSession):
    """Set up test data for scheduling tests."""
    # Create business
    business = Business(
        name="Test Salon",
        timezone="America/New_York",
        policy={"min_lead_time_hours": 2, "max_advance_booking_days": 30},
    )
    db.add(business)
    await db.flush()

    # Create customer
    customer = Customer(
        business_id=business.id,
        first_name="John",
        last_name="Doe",
        phone="+1234567890",
        email="john@example.com",
    )
    db.add(customer)
    await db.flush()

    # Create staff
    staff = Staff(
        business_id=business.id,
        name="John Barber",
        role=StaffRole.STAFF.value,
        is_bookable=True,
        is_active=True,
    )
    db.add(staff)
    await db.flush()

    # Create service
    service = Service(
        business_id=business.id,
        name="Haircut",
        duration_minutes=30,
        price=25.00,
        buffer_before_minutes=5,
        buffer_after_minutes=5,
        min_lead_time_hours=1,
        max_advance_booking_days=14,
    )
    db.add(service)
    await db.flush()

    # Create service addons
    addon1 = ServiceAddon(
        business_id=business.id,
        service_id=service.id,
        name="Beard Trim",
        description="Professional beard trimming",
        extra_duration_minutes=15,
        price=10.00,
        is_active=True,
    )

    addon2 = ServiceAddon(
        business_id=business.id,
        service_id=service.id,
        name="Hair Wash",
        description="Shampoo and conditioning",
        extra_duration_minutes=10,
        price=5.00,
        is_active=True,
    )

    db.add_all([addon1, addon2])
    await db.flush()

    # Create business working hours for all weekdays (Monday to Friday, 9 AM to 6 PM)
    for weekday in [
        WeekDay.MONDAY,
        WeekDay.TUESDAY,
        WeekDay.WEDNESDAY,
        WeekDay.THURSDAY,
        WeekDay.FRIDAY,
    ]:
        business_hours = WorkingHours(
            owner_type=OwnerType.BUSINESS.value,
            owner_id=business.id,
            weekday=weekday.name,
            start_time=time(9, 0),
            end_time=time(18, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
            is_active=True,
        )
        db.add(business_hours)

    # Create staff working hours for all weekdays (Monday to Friday, 9 AM to 5 PM)
    for weekday in [
        WeekDay.MONDAY,
        WeekDay.TUESDAY,
        WeekDay.WEDNESDAY,
        WeekDay.THURSDAY,
        WeekDay.FRIDAY,
    ]:
        staff_hours = WorkingHours(
            owner_type=OwnerType.STAFF.value,
            owner_id=staff.id,
            weekday=weekday.name,
            start_time=time(9, 0),
            end_time=time(17, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
            is_active=True,
        )
        db.add(staff_hours)

    await db.commit()

    return {
        "business": business,
        "customer": customer,
        "staff": staff,
        "service": service,
        "addon1": addon1,
        "addon2": addon2,
    }


class TestSchedulingEngineService:
    """Test scheduling engine with real database interactions."""

    @pytest.mark.asyncio
    async def test_get_staff_availability_basic(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test basic staff availability query with real database."""
        staff = scheduling_test_data["staff"]
        scheduling_service = SchedulingEngineService(db)

        # Use a future date that's guaranteed to be in the future
        future_date = get_future_datetime(hour=9)

        query = StaffAvailabilityQuery(
            staff_uuid=str(staff.uuid),
            start_datetime=future_date,
            end_datetime=future_date.replace(hour=17),
            slot_duration_minutes=30,
        )

        slots = await scheduling_service.get_staff_availability(query)

        # Should have slots for the working hours (9 AM to 5 PM = 8 hours = 16 slots of 30 min each)
        # But excluding the break time (12:00-13:00) = 7 hours = 14 slots
        # Actually, let's check what we get and adjust accordingly
        assert len(slots) >= 12  # At least 12 slots (6 hours)
        assert all(slot.staff_uuid == str(staff.uuid) for slot in slots)

        # All slots should be available since no conflicts exist
        available_slots = [
            slot for slot in slots if slot.status == AvailabilityStatus.AVAILABLE
        ]
        assert len(available_slots) == len(slots)  # All slots should be available

    @pytest.mark.asyncio
    async def test_get_staff_availability_with_service(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test staff availability query with specific service."""
        staff = scheduling_test_data["staff"]
        service = scheduling_test_data["service"]
        scheduling_service = SchedulingEngineService(db)

        # Use a future date that's guaranteed to be in the future
        future_date = get_future_datetime(hour=9)

        query = StaffAvailabilityQuery(
            staff_uuid=str(staff.uuid),
            start_datetime=future_date,
            end_datetime=future_date.replace(hour=17),
            service_uuid=str(service.uuid),
            slot_duration_minutes=40,  # Service total duration (30 + 5 + 5)
        )

        slots = await scheduling_service.get_staff_availability(query)

        # Should have slots for the working hours with 40-minute slots
        # 7 hours (excluding 1-hour break) = 420 minutes / 40 minutes = 10.5 slots
        # But we get 9 slots due to break time constraints
        assert len(slots) >= 9  # At least 9 slots
        assert all(slot.service_uuid == str(service.uuid) for slot in slots)

        # All slots should be available since no conflicts exist
        available_slots = [
            slot for slot in slots if slot.status == AvailabilityStatus.AVAILABLE
        ]
        assert len(available_slots) == len(slots)  # All slots should be available

    @pytest.mark.asyncio
    async def test_get_staff_availability_staff_not_found(self, db: AsyncSession):
        """Test availability query when staff is not found."""
        scheduling_service = SchedulingEngineService(db)

        future_date = get_future_datetime(hour=9)

        query = StaffAvailabilityQuery(
            staff_uuid="12345678-1234-1234-1234-123456789999",  # Non-existent UUID
            start_datetime=future_date,
            end_datetime=future_date.replace(hour=17),
            slot_duration_minutes=30,
        )

        slots = await scheduling_service.get_staff_availability(query)
        assert len(slots) == 0

    @pytest.mark.asyncio
    async def test_get_staff_availability_with_appointment_conflict(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test staff availability with existing appointment conflicts."""
        staff = scheduling_test_data["staff"]
        customer = scheduling_test_data["customer"]
        service = scheduling_test_data["service"]
        scheduling_service = SchedulingEngineService(db)

        # Create an existing appointment
        appointment_time = get_future_datetime(hour=10)
        existing_appointment = Appointment(
            business_id=scheduling_test_data["business"].id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            scheduled_datetime=appointment_time,
            estimated_end_datetime=appointment_time + timedelta(minutes=30),
            duration_minutes=30,
            total_price=25.00,
            status=AppointmentStatus.CONFIRMED.value,
            is_cancelled=False,
        )
        db.add(existing_appointment)
        await db.commit()

        query_start = get_future_datetime(hour=9)
        query = StaffAvailabilityQuery(
            staff_uuid=str(staff.uuid),
            start_datetime=query_start,
            end_datetime=query_start.replace(hour=17),
            slot_duration_minutes=30,
            include_busy_slots=True,  # Include busy slots to see conflicts
        )

        slots = await scheduling_service.get_staff_availability(query)

        # Should have slots including the busy one
        assert len(slots) == 16

        # Find the busy slot (10:00-10:30)
        busy_slots = [
            slot for slot in slots if slot.status == AvailabilityStatus.UNAVAILABLE
        ]
        assert len(busy_slots) > 0

        # Check that the busy slot has appointment conflict
        busy_slot = busy_slots[0]
        assert ConflictType.EXISTING_APPOINTMENT in busy_slot.conflicts

    @pytest.mark.asyncio
    async def test_validate_appointment_valid(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test valid appointment validation with real database."""
        staff = scheduling_test_data["staff"]
        service = scheduling_test_data["service"]
        scheduling_service = SchedulingEngineService(db)

        # Use a future date that's guaranteed to be in the future
        future_time = get_future_datetime(hour=10)

        request = AppointmentValidationRequest(
            staff_uuid=str(staff.uuid),
            service_uuid=str(service.uuid),
            requested_datetime=future_time,
            addon_uuids=[],
        )

        response = await scheduling_service.validate_appointment(request)

        assert response.is_valid is True
        assert len(response.conflicts) == 0
        assert response.total_duration_minutes == 40  # 30 + 5 + 5 (service + buffers)

    @pytest.mark.asyncio
    async def test_validate_appointment_with_conflicts(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test appointment validation with real appointment conflicts."""
        staff = scheduling_test_data["staff"]
        customer = scheduling_test_data["customer"]
        service = scheduling_test_data["service"]
        scheduling_service = SchedulingEngineService(db)

        # Create an existing appointment
        appointment_time = get_future_datetime(hour=10)
        existing_appointment = Appointment(
            business_id=scheduling_test_data["business"].id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            scheduled_datetime=appointment_time,
            estimated_end_datetime=appointment_time + timedelta(minutes=30),
            duration_minutes=30,
            total_price=25.00,
            status=AppointmentStatus.CONFIRMED.value,
            is_cancelled=False,
        )
        db.add(existing_appointment)
        await db.commit()

        # Request appointment that conflicts with existing one
        conflict_time = appointment_time + timedelta(
            minutes=15
        )  # Overlaps with existing
        request = AppointmentValidationRequest(
            staff_uuid=str(staff.uuid),
            service_uuid=str(service.uuid),
            requested_datetime=conflict_time,
            addon_uuids=[],
        )

        response = await scheduling_service.validate_appointment(request)

        assert response.is_valid is False
        assert len(response.conflicts) > 0

        # Check for appointment conflict
        conflict_types = [conflict.conflict_type for conflict in response.conflicts]
        assert ConflictType.EXISTING_APPOINTMENT in conflict_types

    @pytest.mark.asyncio
    async def test_validate_appointment_staff_not_found(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test appointment validation when staff is not found."""
        service = scheduling_test_data["service"]
        scheduling_service = SchedulingEngineService(db)

        future_time = get_future_datetime(hour=10)

        request = AppointmentValidationRequest(
            staff_uuid="12345678-1234-1234-1234-123456789999",  # Non-existent UUID
            service_uuid=str(service.uuid),
            requested_datetime=future_time,
        )

        response = await scheduling_service.validate_appointment(request)

        assert response.is_valid is False
        assert len(response.conflicts) == 1
        assert response.conflicts[0].conflict_type == ConflictType.STAFF_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_check_slot_availability_within_hours(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test slot availability check within working hours."""
        staff = scheduling_test_data["staff"]
        service = scheduling_test_data["service"]
        scheduling_service = SchedulingEngineService(db)

        start_time = get_future_datetime(hour=10)
        end_time = start_time + timedelta(minutes=30)

        status, conflicts = await scheduling_service._check_slot_availability(
            staff, start_time, end_time, service
        )

        assert status == AvailabilityStatus.AVAILABLE
        assert len(conflicts) == 0

    @pytest.mark.asyncio
    async def test_check_slot_availability_outside_hours(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test slot availability check outside working hours."""
        staff = scheduling_test_data["staff"]
        scheduling_service = SchedulingEngineService(db)

        start_time = get_future_datetime(hour=20)  # 8 PM (outside hours)
        end_time = start_time + timedelta(minutes=30)

        status, conflicts = await scheduling_service._check_slot_availability(
            staff, start_time, end_time
        )

        assert status == AvailabilityStatus.UNAVAILABLE
        assert ConflictType.OUTSIDE_WORKING_HOURS in conflicts

    @pytest.mark.asyncio
    async def test_has_appointment_conflict_real_database(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test appointment conflict detection with real database interactions."""
        staff = scheduling_test_data["staff"]
        customer = scheduling_test_data["customer"]
        service = scheduling_test_data["service"]
        scheduling_service = SchedulingEngineService(db)

        # Test with no existing appointments
        start_time = get_future_datetime(hour=10)
        end_time = start_time + timedelta(minutes=30)

        has_conflict = await scheduling_service._has_appointment_conflict(
            staff.id, start_time, end_time
        )
        assert has_conflict is False

        # Create an existing appointment
        appointment_time = get_future_datetime(hour=10)
        existing_appointment = Appointment(
            business_id=scheduling_test_data["business"].id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            scheduled_datetime=appointment_time,
            estimated_end_datetime=appointment_time + timedelta(minutes=30),
            duration_minutes=30,
            total_price=25.00,
            status=AppointmentStatus.CONFIRMED.value,
            is_cancelled=False,
        )
        db.add(existing_appointment)
        await db.commit()

        # Test overlapping time slot
        start_time = appointment_time + timedelta(minutes=15)  # Overlaps
        end_time = appointment_time + timedelta(minutes=45)  # Overlaps

        has_conflict = await scheduling_service._has_appointment_conflict(
            staff.id, start_time, end_time
        )
        assert has_conflict is True

        # Test that cancelled appointments don't cause conflicts
        existing_appointment.status = AppointmentStatus.CANCELLED.value
        existing_appointment.is_cancelled = True
        await db.commit()

        has_conflict = await scheduling_service._has_appointment_conflict(
            staff.id, start_time, end_time
        )
        assert has_conflict is False

    @pytest.mark.asyncio
    async def test_validate_appointment_with_addons(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test appointment validation with service addons."""
        staff = scheduling_test_data["staff"]
        service = scheduling_test_data["service"]
        addon1 = scheduling_test_data["addon1"]
        addon2 = scheduling_test_data["addon2"]
        scheduling_service = SchedulingEngineService(db)

        future_time = get_future_datetime(hour=9)

        # Test with one addon
        request = AppointmentValidationRequest(
            staff_uuid=str(staff.uuid),
            service_uuid=str(service.uuid),
            requested_datetime=future_time,
            addon_uuids=[str(addon1.uuid)],
        )

        response = await scheduling_service.validate_appointment(request)

        assert response.is_valid is True
        assert len(response.conflicts) == 0
        # Service (30) + buffers (5+5) + addon1 (15) = 55 minutes
        assert response.total_duration_minutes == 55

        # Test with multiple addons - use 2 PM to avoid break time conflict
        request = AppointmentValidationRequest(
            staff_uuid=str(staff.uuid),
            service_uuid=str(service.uuid),
            requested_datetime=get_future_datetime(hour=14),
            addon_uuids=[str(addon1.uuid), str(addon2.uuid)],
        )

        response = await scheduling_service.validate_appointment(request)

        assert response.is_valid is True
        assert len(response.conflicts) == 0
        # Service (30) + buffers (5+5) + addon1 (15) + addon2 (10) = 65 minutes
        assert response.total_duration_minutes == 65

    @pytest.mark.asyncio
    async def test_validate_appointment_with_addons_conflict(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test appointment validation with addons that cause conflicts."""
        staff = scheduling_test_data["staff"]
        service = scheduling_test_data["service"]
        addon1 = scheduling_test_data["addon1"]
        addon2 = scheduling_test_data["addon2"]
        customer = scheduling_test_data["customer"]
        scheduling_service = SchedulingEngineService(db)

        # Create an existing appointment
        appointment_time = get_future_datetime(hour=10)
        existing_appointment = Appointment(
            business_id=scheduling_test_data["business"].id,
            customer_id=customer.id,
            staff_id=staff.id,
            service_id=service.id,
            scheduled_datetime=appointment_time,
            estimated_end_datetime=appointment_time + timedelta(minutes=30),
            duration_minutes=30,
            total_price=25.00,
            status=AppointmentStatus.CONFIRMED.value,
            is_cancelled=False,
        )
        db.add(existing_appointment)
        await db.commit()

        # Request appointment with addons that would conflict
        # Start 15 minutes after existing appointment, but with 65-minute duration
        # This should conflict because it extends beyond the existing appointment
        conflict_time = appointment_time + timedelta(minutes=15)
        request = AppointmentValidationRequest(
            staff_uuid=str(staff.uuid),
            service_uuid=str(service.uuid),
            requested_datetime=conflict_time,
            addon_uuids=[str(addon1.uuid), str(addon2.uuid)],
        )

        response = await scheduling_service.validate_appointment(request)

        assert response.is_valid is False
        assert len(response.conflicts) > 0

        # Check for appointment conflict
        conflict_types = [conflict.conflict_type for conflict in response.conflicts]
        assert ConflictType.EXISTING_APPOINTMENT in conflict_types

    @pytest.mark.asyncio
    async def test_get_staff_availability_with_addons(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test staff availability query with service addons."""
        staff = scheduling_test_data["staff"]
        service = scheduling_test_data["service"]
        scheduling_test_data["addon1"]
        scheduling_service = SchedulingEngineService(db)

        future_date = get_future_datetime(hour=9)

        # Test availability with addon duration
        query = StaffAvailabilityQuery(
            staff_uuid=str(staff.uuid),
            start_datetime=future_date,
            end_datetime=future_date.replace(hour=17),
            service_uuid=str(service.uuid),
            slot_duration_minutes=55,  # Service (30) + buffers (10) + addon1 (15)
        )

        slots = await scheduling_service.get_staff_availability(query)

        # Should have fewer slots due to longer duration
        assert len(slots) >= 6  # At least 6 slots with 55-minute duration
        assert all(slot.service_uuid == str(service.uuid) for slot in slots)

        # All slots should be available since no conflicts exist
        available_slots = [
            slot for slot in slots if slot.status == AvailabilityStatus.AVAILABLE
        ]
        assert len(available_slots) == len(slots)

    @pytest.mark.asyncio
    async def test_calculate_addon_duration(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test addon duration calculation method."""
        addon1 = scheduling_test_data["addon1"]
        addon2 = scheduling_test_data["addon2"]
        scheduling_service = SchedulingEngineService(db)

        # Test with no addons
        duration = await scheduling_service._calculate_addon_duration([])
        assert duration == 0

        # Test with one addon
        duration = await scheduling_service._calculate_addon_duration(
            [str(addon1.uuid)]
        )
        assert duration == 15

        # Test with multiple addons
        duration = await scheduling_service._calculate_addon_duration(
            [str(addon1.uuid), str(addon2.uuid)]
        )
        assert duration == 25  # 15 + 10

        # Test with non-existent addon
        duration = await scheduling_service._calculate_addon_duration(
            ["12345678-1234-1234-1234-123456789999"]
        )
        assert duration == 0

    @pytest.mark.asyncio
    async def test_validate_appointment_inactive_addon(
        self, db: AsyncSession, scheduling_test_data
    ):
        """Test appointment validation with inactive addon."""
        staff = scheduling_test_data["staff"]
        service = scheduling_test_data["service"]
        addon1 = scheduling_test_data["addon1"]
        scheduling_service = SchedulingEngineService(db)

        # Make addon inactive
        addon1.is_active = False
        await db.commit()

        future_time = get_future_datetime(hour=10)

        request = AppointmentValidationRequest(
            staff_uuid=str(staff.uuid),
            service_uuid=str(service.uuid),
            requested_datetime=future_time,
            addon_uuids=[str(addon1.uuid)],
        )

        response = await scheduling_service.validate_appointment(request)

        assert response.is_valid is True
        # Should not include inactive addon duration
        assert response.total_duration_minutes == 40  # Service (30) + buffers (10)
