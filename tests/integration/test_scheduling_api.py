from datetime import datetime, time, timedelta, timezone

import pytest
from httpx import AsyncClient

from app.main import app
from app.models.availability_override import AvailabilityOverride, OverrideType
from app.models.business import Business
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.models.staff import Staff, StaffRole
from app.models.time_off import TimeOff, TimeOffStatus, TimeOffType
from app.models.working_hours import OwnerType, WeekDay, WorkingHours


@pytest.fixture
async def setup_test_data(db):
    """Set up test data for scheduling integration tests."""

    # Create business
    business = Business(
        name="Test Barbershop",
        timezone="America/New_York",
        policy={"min_lead_time_hours": 2, "max_advance_booking_days": 30},
    )
    db.add(business)
    await db.flush()

    # Create service category
    category = ServiceCategory(
        business_id=business.id, name="Haircuts", description="Hair cutting services"
    )
    db.add(category)
    await db.flush()

    # Create staff
    staff = Staff(
        business_id=business.id,
        name="John Barber",
        email="john@testbarbershop.com",
        role=StaffRole.STAFF.value,
        is_bookable=True,
        is_active=True,
    )
    db.add(staff)
    await db.flush()

    # Create service
    service = Service(
        business_id=business.id,
        category_id=category.id,
        name="Classic Haircut",
        duration_minutes=30,
        price=25.00,
        buffer_before_minutes=5,
        buffer_after_minutes=5,
        min_lead_time_hours=1,
        max_advance_booking_days=14,
    )
    db.add(service)
    await db.flush()

    # Create business working hours (Monday to Friday, 9 AM to 6 PM)
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
            weekday=str(weekday.value),
            start_time=time(9, 0),
            end_time=time(18, 0),
            break_start_time=time(12, 0),
            break_end_time=time(13, 0),
            is_active=True,
        )
        db.add(business_hours)

    # Create staff working hours (Monday to Friday, 9 AM to 5 PM)
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
            weekday=str(weekday.value),
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
        "staff": staff,
        "service": service,
        "category": category,
    }


class TestSchedulingAPIEndpoints:
    """Integration tests for scheduling API endpoints."""

    @pytest.mark.asyncio
    async def test_get_staff_availability_success(self, setup_test_data):
        """Test successful staff availability retrieval."""
        staff = setup_test_data["staff"]

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/staff/availability",
                params={
                    "staff_uuid": str(staff.uuid),
                    "start_datetime": "2024-01-15T09:00:00+00:00",  # Monday 9 AM
                    "end_datetime": "2024-01-15T17:00:00+00:00",  # Monday 5 PM
                    "slot_duration_minutes": 30,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert "slots" in data
        assert isinstance(data["slots"], list)

        if len(data["slots"]) > 0:
            # Check slot structure
            first_slot = data["slots"][0]
            assert "start_datetime" in first_slot
            assert "end_datetime" in first_slot
            assert "status" in first_slot
            assert "staff_uuid" in first_slot
            assert first_slot["staff_uuid"] == str(staff.uuid)

    @pytest.mark.asyncio
    async def test_get_staff_availability_with_service(self, setup_test_data):
        """Test staff availability retrieval with specific service."""
        staff = setup_test_data["staff"]
        service = setup_test_data["service"]

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/staff/availability",
                params={
                    "staff_uuid": str(staff.uuid),
                    "start_datetime": "2024-01-15T09:00:00+00:00",
                    "end_datetime": "2024-01-15T17:00:00+00:00",
                    "service_uuid": str(service.uuid),
                    "slot_duration_minutes": 40,  # Service total duration
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert "slots" in data
        assert isinstance(data["slots"], list)

        # Check that service UUID is included if slots exist
        for slot in data["slots"]:
            if slot.get("service_uuid"):
                assert slot["service_uuid"] == str(service.uuid)

    @pytest.mark.asyncio
    async def test_get_staff_availability_staff_not_found(self):
        """Test staff availability when staff is not found."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/staff/availability",
                params={
                    "staff_uuid": "12345678-1234-1234-1234-123456789999",
                    "start_datetime": "2024-01-15T09:00:00+00:00",
                    "end_datetime": "2024-01-15T17:00:00+00:00",
                    "slot_duration_minutes": 30,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert "slots" in data
        assert len(data["slots"]) == 0

    @pytest.mark.asyncio
    async def test_validate_appointment_success(self, setup_test_data):
        """Test successful appointment validation."""
        staff = setup_test_data["staff"]
        service = setup_test_data["service"]

        # Request appointment 3 hours in future (meets lead time)
        future_time = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(
            hours=3
        )
        # Make sure it's a weekday and within working hours
        if future_time.weekday() >= 5:  # Weekend
            future_time += timedelta(days=2)  # Move to Monday
        future_time = future_time.replace(hour=10, minute=0, second=0, microsecond=0)

        request_data = {
            "staff_uuid": str(staff.uuid),
            "service_uuid": str(service.uuid),
            "requested_datetime": future_time.isoformat(),
            "addon_uuids": [],
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/scheduling/appointments/validate", json=request_data
            )

        assert response.status_code == 200
        data = response.json()

        assert "is_valid" in data
        assert "conflicts" in data
        assert "total_duration_minutes" in data
        assert "estimated_end_time" in data

        # Check the response structure
        assert isinstance(data["conflicts"], list)
        assert data["total_duration_minutes"] == 40  # 30 + 5 + 5

    @pytest.mark.asyncio
    async def test_validate_appointment_lead_time_violation(self, setup_test_data):
        """Test appointment validation with lead time violation."""
        staff = setup_test_data["staff"]
        service = setup_test_data["service"]

        # Request appointment in 30 minutes (violates 1-hour lead time)
        future_time = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(
            minutes=30
        )
        if future_time.weekday() >= 5:  # Weekend
            future_time += timedelta(days=2)
        future_time = future_time.replace(hour=10, minute=0, second=0, microsecond=0)

        request_data = {
            "staff_uuid": str(staff.uuid),
            "service_uuid": str(service.uuid),
            "requested_datetime": future_time.isoformat(),
            "addon_uuids": [],
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/scheduling/appointments/validate", json=request_data
            )

        assert response.status_code == 200
        data = response.json()

        # Should be invalid due to lead time violation
        assert data["is_valid"] is False
        assert len(data["conflicts"]) > 0

        # Check for lead time conflict
        conflict_types = [c["conflict_type"] for c in data["conflicts"]]
        assert "lead_time_violation" in conflict_types

    @pytest.mark.asyncio
    async def test_validate_appointment_outside_hours(self, setup_test_data):
        """Test appointment validation outside working hours."""
        staff = setup_test_data["staff"]
        service = setup_test_data["service"]

        # Request appointment at 8 PM (outside working hours)
        future_time = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(days=1)
        if future_time.weekday() >= 5:  # Weekend
            future_time += timedelta(days=2)
        future_time = future_time.replace(hour=20, minute=0, second=0, microsecond=0)

        request_data = {
            "staff_uuid": str(staff.uuid),
            "service_uuid": str(service.uuid),
            "requested_datetime": future_time.isoformat(),
            "addon_uuids": [],
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/scheduling/appointments/validate", json=request_data
            )

        assert response.status_code == 200
        data = response.json()

        # Should be invalid due to being outside working hours
        assert data["is_valid"] is False
        assert len(data["conflicts"]) > 0

        # Check for working hours conflict
        conflict_types = [c["conflict_type"] for c in data["conflicts"]]
        assert "outside_working_hours" in conflict_types

    @pytest.mark.asyncio
    async def test_validate_appointment_staff_not_found(self, setup_test_data):
        """Test appointment validation when staff is not found."""
        service = setup_test_data["service"]

        future_time = datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(
            hours=3
        )
        request_data = {
            "staff_uuid": "12345678-1234-1234-1234-123456789999",
            "service_uuid": str(service.uuid),
            "requested_datetime": future_time.isoformat(),
            "addon_uuids": [],
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/scheduling/appointments/validate", json=request_data
            )

        assert response.status_code == 200
        data = response.json()

        assert data["is_valid"] is False
        assert len(data["conflicts"]) > 0

        conflict_types = [c["conflict_type"] for c in data["conflicts"]]
        assert "staff_unavailable" in conflict_types

    @pytest.mark.asyncio
    async def test_get_business_hours_success(self, setup_test_data):
        """Test successful business hours retrieval."""
        business = setup_test_data["business"]

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/business/hours",
                params={
                    "business_uuid": str(business.uuid),
                    "date": "2024-01-15T00:00:00+00:00",  # Monday
                    "include_breaks": True,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert "is_open" in data
        assert "weekday" in data
        assert data["weekday"] == "MONDAY"

        if data["is_open"]:
            assert "hours" in data
            assert data["hours"]["start_time"] == "09:00:00"
            assert data["hours"]["end_time"] == "18:00:00"
            assert "break" in data["hours"]

    @pytest.mark.asyncio
    async def test_get_business_hours_closed_day(self, setup_test_data):
        """Test business hours retrieval for closed day."""
        business = setup_test_data["business"]

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/business/hours",
                params={
                    "business_uuid": str(business.uuid),
                    "date": "2024-01-14T00:00:00+00:00",  # Sunday (not configured)
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert data["is_open"] is False
        assert data["weekday"] == "SUNDAY"
        assert data["hours"] is None

    @pytest.mark.asyncio
    async def test_get_business_hours_business_not_found(self):
        """Test business hours retrieval when business is not found."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/business/hours",
                params={
                    "business_uuid": "12345678-1234-1234-1234-123456789999",
                    "date": "2024-01-15T00:00:00+00:00",
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Should return empty dict when business not found
        assert data == {}

    @pytest.mark.asyncio
    async def test_get_staff_schedule_success(self, setup_test_data):
        """Test successful staff schedule retrieval."""
        staff = setup_test_data["staff"]

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/staff/schedule",
                params={
                    "staff_uuid": str(staff.uuid),
                    "start_date": "2024-01-15T00:00:00+00:00",  # Monday
                    "end_date": "2024-01-19T23:59:59+00:00",  # Friday
                    "include_appointments": True,
                    "include_time_off": True,
                    "include_availability_overrides": True,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert "staff_uuid" in data
        assert data["staff_uuid"] == str(staff.uuid)
        assert "start_date" in data
        assert "end_date" in data
        assert "working_hours" in data
        assert "time_off" in data
        assert "availability_overrides" in data
        assert "appointments" in data

        # Should have working hours for weekdays
        assert isinstance(data["working_hours"], list)

    @pytest.mark.asyncio
    async def test_get_staff_schedule_with_time_off(self, setup_test_data, db):
        """Test staff schedule retrieval with time off."""
        staff = setup_test_data["staff"]

        # Add time off for the staff
        time_off = TimeOff(
            owner_type=OwnerType.STAFF.value,
            owner_id=staff.id,
            start_datetime=datetime(
                2024, 1, 16, 9, 0, tzinfo=timezone.utc
            ),  # Tuesday 9 AM
            end_datetime=datetime(
                2024, 1, 16, 17, 0, tzinfo=timezone.utc
            ),  # Tuesday 5 PM
            type=TimeOffType.PERSONAL.value,
            reason="Doctor appointment",
            status=TimeOffStatus.APPROVED.value,
            is_all_day=True,
        )
        db.add(time_off)
        await db.commit()

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/staff/schedule",
                params={
                    "staff_uuid": str(staff.uuid),
                    "start_date": "2024-01-15T00:00:00+00:00",
                    "end_date": "2024-01-19T23:59:59+00:00",
                    "include_time_off": True,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert len(data["time_off"]) > 0

        time_off_entry = data["time_off"][0]
        assert time_off_entry["type"] == "PERSONAL"
        assert time_off_entry["reason"] == "Doctor appointment"
        assert time_off_entry["is_all_day"] is True

    @pytest.mark.asyncio
    async def test_get_staff_schedule_with_availability_override(
        self, setup_test_data, db
    ):
        """Test staff schedule retrieval with availability overrides."""
        staff = setup_test_data["staff"]

        # Add availability override
        override = AvailabilityOverride(
            staff_id=staff.id,
            override_type=OverrideType.AVAILABLE.value,
            start_datetime=datetime(
                2024, 1, 14, 10, 0, tzinfo=timezone.utc
            ),  # Sunday 10 AM
            end_datetime=datetime(
                2024, 1, 14, 16, 0, tzinfo=timezone.utc
            ),  # Sunday 4 PM
            title="Special Sunday Hours",
            reason="Special event coverage",
            is_active=True,
            allow_new_bookings=True,
            created_by_staff_id=staff.id,
        )
        db.add(override)
        await db.commit()

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/staff/schedule",
                params={
                    "staff_uuid": str(staff.uuid),
                    "start_date": "2024-01-14T00:00:00+00:00",  # Sunday
                    "end_date": "2024-01-14T23:59:59+00:00",  # Sunday
                    "include_availability_overrides": True,
                },
            )

        assert response.status_code == 200
        data = response.json()

        assert len(data["availability_overrides"]) > 0

        override_entry = data["availability_overrides"][0]
        assert override_entry["type"] == "AVAILABLE"
        assert override_entry["title"] == "Special Sunday Hours"
        assert override_entry["reason"] == "Special event coverage"
        assert override_entry["allow_new_bookings"] is True

    @pytest.mark.asyncio
    async def test_get_staff_schedule_staff_not_found(self):
        """Test staff schedule retrieval when staff is not found."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/scheduling/staff/schedule",
                params={
                    "staff_uuid": "12345678-1234-1234-1234-123456789999",
                    "start_date": "2024-01-15T00:00:00+00:00",
                    "end_date": "2024-01-19T23:59:59+00:00",
                },
            )

        assert response.status_code == 200
        data = response.json()

        # Should return empty dict when staff not found
        assert data == {}

    @pytest.mark.asyncio
    async def test_validate_appointment_with_alternatives(self, setup_test_data, db):
        """Test appointment validation that provides alternative slots."""
        staff = setup_test_data["staff"]
        service = setup_test_data["service"]

        # Add time off to conflict with the requested time
        time_off = TimeOff(
            owner_type=OwnerType.STAFF.value,
            owner_id=staff.id,
            start_datetime=datetime(
                2024, 1, 15, 10, 0, tzinfo=timezone.utc
            ),  # Monday 10 AM
            end_datetime=datetime(
                2024, 1, 15, 11, 0, tzinfo=timezone.utc
            ),  # Monday 11 AM
            type=TimeOffType.PERSONAL.value,
            status=TimeOffStatus.APPROVED.value,
        )
        print(f"TIME OFF {time_off}")
        db.add(time_off)
        await db.commit()

        # Request appointment during time off
        request_data = {
            "staff_uuid": str(staff.uuid),
            "service_uuid": str(service.uuid),
            "requested_datetime": "2024-01-15T10:00:00+00:00",
            "addon_uuids": [],
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/scheduling/appointments/validate", json=request_data
            )

        assert response.status_code == 200
        data = response.json()

        assert data["is_valid"] is False
        assert len(data["conflicts"]) > 0

        # Should provide alternative slots
        if "alternative_slots" in data:
            assert isinstance(data["alternative_slots"], list)
            # Alternative slots should be available times
            for slot in data["alternative_slots"]:
                assert slot["status"] == "available"
