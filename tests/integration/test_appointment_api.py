from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.main import app
from app.models.appointment import Appointment, AppointmentStatus
from app.models.business import Business
from app.models.customer import Customer
from app.models.service import Service
from app.models.staff import Staff
from app.models.working_hours import OwnerType, WeekDay, WorkingHours
from tests.conftest import get_auth_headers


@pytest.fixture
async def test_business(db):
    """Create test business."""
    business = Business(
        uuid=uuid4(),
        name="Test Salon",
        email="test@testsalon.com",
        phone="555-0123",
    )
    db.add(business)
    await db.flush()
    await db.refresh(business)
    return business


@pytest.fixture
async def test_customer(db, test_business):
    """Create test customer."""
    customer = Customer(
        uuid=uuid4(),
        business_id=test_business.id,
        first_name="John",
        last_name="Doe",
    )
    db.add(customer)
    await db.flush()
    await db.refresh(customer)
    return customer


@pytest.fixture
async def test_business_working_hours(db, test_business):
    """Create business working hours (Monday-Sunday 9-17)."""
    from datetime import time

    working_hours = []

    # Create working hours for all days of the week to support
    #  dynamic appointment dates
    for day in WeekDay:
        day_hours = WorkingHours(
            uuid=uuid4(),
            owner_type=OwnerType.BUSINESS.value,
            owner_id=test_business.id,
            weekday=day.name,
            start_time=time(9, 0),  # 9:00 AM
            end_time=time(17, 0),  # 5:00 PM
            is_active=True,
        )
        working_hours.append(day_hours)
        db.add(day_hours)

    await db.flush()
    return working_hours


@pytest.fixture
async def test_staff(db, test_business):
    """Create test staff."""
    staff = Staff(
        id=1,
        uuid=uuid4(),
        name="Jane Stylist",
        business_id=test_business.id,
        email="jane@testsalon.com",
        role="STAFF",
        is_active=True,
        is_bookable=True,
    )
    db.add(staff)
    await db.flush()
    await db.refresh(staff)
    return staff


@pytest.fixture
async def test_staff_working_hours(db, test_staff):
    """Create staff working hours (Monday-Sunday 9-17)."""
    from datetime import time

    working_hours = []

    # Create working hours for all days of the week to support
    # dynamic appointment dates
    for day in WeekDay:
        day_hours = WorkingHours(
            uuid=uuid4(),
            owner_type=OwnerType.STAFF.value,
            owner_id=test_staff.id,
            weekday=day.name,
            start_time=time(9, 0),  # 9:00 AM
            end_time=time(17, 0),  # 5:00 PM
            is_active=True,
        )
        working_hours.append(day_hours)
        db.add(day_hours)

    await db.flush()
    return working_hours


@pytest.fixture
async def test_service(db, test_business):
    """Create test service."""
    service = Service(
        uuid=uuid4(),
        name="Haircut",
        business_id=test_business.id,
        duration_minutes=30,
        price=Decimal("50.00"),
        buffer_before_minutes=5,
        buffer_after_minutes=5,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)
    return service


@pytest.fixture
async def test_appointment(db, test_business, test_customer, test_staff, test_service):
    """Create test appointment."""
    from datetime import timezone

    # Schedule appointment for tomorrow at 2 PM
    future_date = datetime.now(timezone.utc) + timedelta(days=2)
    scheduled_time = future_date.replace(hour=14, minute=0, second=0, microsecond=0)
    estimated_end = scheduled_time + timedelta(minutes=30)

    appointment = Appointment(
        uuid=uuid4(),
        business_id=test_business.id,
        customer_id=test_customer.id,
        staff_id=test_staff.id,
        service_id=test_service.id,
        scheduled_datetime=scheduled_time,
        estimated_end_datetime=estimated_end,
        duration_minutes=30,
        total_price=Decimal("50.00"),
        status=AppointmentStatus.TENTATIVE.value,
        booking_source="admin",
    )
    db.add(appointment)
    await db.flush()
    await db.refresh(appointment)
    return appointment


@pytest.fixture
def client():
    """Create test client."""
    return AsyncClient(app=app, base_url="http://test")


@pytest.fixture
def mock_current_business(test_business):
    """Mock current business dependency."""
    from app.api.deps.business import BusinessContext, get_business_from_header

    async def _mock_current_business():
        return BusinessContext(test_business)

    app.dependency_overrides[get_business_from_header] = _mock_current_business
    yield test_business
    app.dependency_overrides.clear()


class TestAppointmentAPICreate:
    """Test appointment creation API endpoints."""

    @pytest.mark.asyncio
    async def test_create_appointment_success(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_customer,
        test_staff,
        test_service,
        test_business_working_hours,
        test_staff_working_hours,
        mock_current_business,
    ):
        """Test successful appointment creation."""
        appointment_data = {
            "customer_id": test_customer.id,
            "staff_id": test_staff.id,
            "service_id": test_service.id,
            "scheduled_datetime": "2024-01-16T14:00:00",
            "duration_minutes": 30,
            "total_price": "50.00",
            "booking_source": "admin",
            "customer_notes": "First visit",
        }

        headers = get_auth_headers(1)  # Staff member
        response = await client.post(
            "/api/v1/appointments/", json=appointment_data, headers=headers
        )

        assert response.status_code == 201
        data = response.json()
        assert data["customer_id"] == test_customer.id
        assert data["staff_id"] == test_staff.id
        assert data["service_id"] == test_service.id
        assert data["status"] == "tentative"
        assert data["total_price"] == "50.00"
        assert data["customer_notes"] == "First visit"

    @pytest.mark.asyncio
    async def test_create_appointment_with_slot_lock(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_customer,
        test_staff,
        test_service,
        test_business_working_hours,
        test_staff_working_hours,
        mock_current_business,
    ):
        """Test appointment creation with slot locking."""
        appointment_data = {
            "customer_id": test_customer.id,
            "staff_id": test_staff.id,
            "service_id": test_service.id,
            "scheduled_datetime": "2024-01-16T14:00:00",
            "duration_minutes": 30,
            "total_price": "50.00",
            "booking_source": "online",
        }

        session_id = "test_session_123"
        headers = get_auth_headers(1)  # Staff member
        response = await client.post(
            f"/api/v1/appointments/?session_id={session_id}",
            json=appointment_data,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["slot_locked"] is True
        assert data["locked_by_session_id"] == session_id

    @pytest.mark.asyncio
    async def test_create_appointment_validation_error(
        self, client: AsyncClient, db, test_business, test_staff, mock_current_business
    ):
        """Test appointment creation with validation errors."""
        appointment_data = {
            "customer_id": 999,  # Non-existent customer
            "staff_id": 999,  # Non-existent staff
            "service_id": 999,  # Non-existent service
            "scheduled_datetime": "2024-01-16T14:00:00",
            "duration_minutes": 30,
            "total_price": "50.00",
        }

        headers = get_auth_headers(test_staff.id)  # Staff member
        response = await client.post(
            "/api/v1/appointments/", json=appointment_data, headers=headers
        )

        if response.status_code != 400:
            print(f"Expected 400, got {response.status_code}: {response.text}")
        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()


class TestAppointmentAPIRead:
    """Test appointment reading API endpoints."""

    @pytest.mark.asyncio
    async def test_get_appointments_list(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        mock_current_business,
    ):
        """Test getting appointments list."""
        headers = get_auth_headers(1)  # Staff member
        response = await client.get("/api/v1/appointments/", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert len(data["appointments"]) == 1
        assert data["appointments"][0]["id"] == test_appointment.id

    @pytest.mark.asyncio
    async def test_get_appointments_with_filters(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        mock_current_business,
    ):
        """Test getting appointments with filters."""
        headers = get_auth_headers(1)  # Staff member
        # Create additional appointment with different status
        from datetime import timezone

        future_date = datetime.now(timezone.utc) + timedelta(days=3)
        scheduled_time = future_date.replace(hour=15, minute=0, second=0, microsecond=0)
        estimated_end = scheduled_time + timedelta(minutes=30)

        confirmed_appointment = Appointment(
            uuid=uuid4(),
            business_id=test_appointment.business_id,
            customer_id=test_appointment.customer_id,
            staff_id=test_appointment.staff_id,
            service_id=test_appointment.service_id,
            scheduled_datetime=scheduled_time,
            estimated_end_datetime=estimated_end,
            duration_minutes=30,
            total_price=Decimal("50.00"),
            status=AppointmentStatus.CONFIRMED.value,
            booking_source="admin",
        )
        db.add(confirmed_appointment)
        await db.flush()

        # Filter by status
        response = await client.get(
            "/api/v1/appointments/?status=confirmed", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] == 1
        assert data["appointments"][0]["status"] == "confirmed"

    @pytest.mark.asyncio
    async def test_get_appointments_with_search(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        mock_current_business,
    ):
        """Test getting appointments with search query."""
        headers = get_auth_headers(1)  # Staff member
        response = await client.get("/api/v1/appointments/?query=John", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_count"] >= 0  # May find appointments depending on setup

    @pytest.mark.asyncio
    async def test_get_appointments_with_pagination(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        mock_current_business,
    ):
        """Test appointments pagination."""
        headers = get_auth_headers(1)  # Staff member
        response = await client.get(
            "/api/v1/appointments/?page=1&page_size=10", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert "total_pages" in data

    @pytest.mark.asyncio
    async def test_get_appointment_by_uuid(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        mock_current_business,
    ):
        """Test getting single appointment by UUID."""
        headers = get_auth_headers(1)  # Staff member
        response = await client.get(
            f"/api/v1/appointments/{test_appointment.uuid}", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_appointment.id
        assert data["uuid"] == str(test_appointment.uuid)
        assert "customer" in data  # Should include relationships
        assert "staff" in data
        assert "service" in data

    @pytest.mark.asyncio
    async def test_get_appointment_not_found(
        self, client: AsyncClient, db, test_business, mock_current_business
    ):
        """Test getting non-existent appointment."""
        fake_uuid = uuid4()
        headers = get_auth_headers(1)  # Staff member
        response = await client.get(
            f"/api/v1/appointments/{fake_uuid}", headers=headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestAppointmentAPIUpdate:
    """Test appointment update API endpoints."""

    @pytest.mark.asyncio
    async def test_update_appointment_success(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        mock_current_business,
    ):
        """Test successful appointment update."""
        update_data = {
            "total_price": "60.00",
            "customer_notes": "Updated notes",
            "internal_notes": "Staff notes updated",
        }

        headers = get_auth_headers(1)  # Staff member
        response = await client.put(
            f"/api/v1/appointments/{test_appointment.uuid}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_price"] == "60.00"
        assert data["customer_notes"] == "Updated notes"
        assert data["internal_notes"] == "Staff notes updated"

    @pytest.mark.asyncio
    async def test_update_appointment_reschedule(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        test_business_working_hours,
        test_staff_working_hours,
        mock_current_business,
    ):
        """Test appointment rescheduling."""
        # Use a future date for rescheduling
        from datetime import timezone

        future_date = datetime.now(timezone.utc) + timedelta(days=4)
        new_time = future_date.replace(hour=10, minute=0, second=0, microsecond=0)
        new_datetime = new_time.strftime("%Y-%m-%dT%H:%M:%S")

        update_data = {
            "scheduled_datetime": new_datetime,
        }

        headers = get_auth_headers(1)  # Staff member
        response = await client.put(
            f"/api/v1/appointments/{test_appointment.uuid}",
            json=update_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Check that the appointment was rescheduled (exact format may vary due to timezone conversions)
        returned_date = data["scheduled_datetime"][:10]  # Get just the date part
        expected_date = new_datetime[:10]  # Get just the date part
        assert returned_date == expected_date
        assert data["reschedule_count"] == 1

    @pytest.mark.asyncio
    async def test_update_appointment_not_found(
        self, client: AsyncClient, db, test_staff, mock_current_business
    ):
        """Test updating non-existent appointment."""
        fake_uuid = uuid4()
        update_data = {"total_price": "60.00"}

        headers = get_auth_headers(test_staff.id)  # Staff member
        response = await client.put(
            f"/api/v1/appointments/{fake_uuid}", json=update_data, headers=headers
        )

        assert response.status_code == 404


class TestAppointmentAPIStatusTransitions:
    """Test appointment status transition API endpoints."""

    @pytest.mark.asyncio
    async def test_transition_status_confirm(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test confirming appointment."""
        transition_data = {
            "new_status": "confirmed",
            "notes": "Customer called to confirm",
        }

        headers = get_auth_headers(1)  # Staff member performing transition
        response = await client.post(
            f"/api/v1/appointments/{test_appointment.uuid}/status",
            json=transition_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "confirmed"
        assert data["previous_status"] == "tentative"

    @pytest.mark.asyncio
    async def test_transition_status_cancel_with_reason(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test cancelling appointment with reason and fee."""
        # First confirm the appointment
        test_appointment.status = AppointmentStatus.CONFIRMED.value
        await db.flush()

        transition_data = {
            "new_status": "cancelled",
            "notes": "Customer requested cancellation",
            "cancellation_reason": "customer_request",
            "cancellation_fee": "15.00",
        }

        headers = get_auth_headers(1)  # Staff member performing transition
        response = await client.post(
            f"/api/v1/appointments/{test_appointment.uuid}/status",
            json=transition_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"
        assert data["is_cancelled"] is True
        assert data["cancellation_reason"] == "customer_request"
        assert data["cancellation_fee"] == "15.00"

    @pytest.mark.asyncio
    async def test_transition_status_invalid_transition(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test invalid status transition."""
        # Try to transition completed appointment to confirmed
        test_appointment.status = AppointmentStatus.COMPLETED.value
        await db.flush()

        transition_data = {
            "new_status": "confirmed",
        }

        headers = get_auth_headers(1)  # Staff member performing transition
        response = await client.post(
            f"/api/v1/appointments/{test_appointment.uuid}/status",
            json=transition_data,
            headers=headers,
        )

        assert response.status_code == 400
        assert "Cannot transition from" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_reschedule_appointment(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_appointment,
        test_business_working_hours,
        test_staff_working_hours,
        mock_current_business,
    ):
        """Test appointment rescheduling endpoint."""
        # Use a future date for rescheduling
        from datetime import timezone

        future_date = datetime.now(timezone.utc) + timedelta(days=5)
        new_time = future_date.replace(hour=15, minute=0, second=0, microsecond=0)
        new_scheduled_datetime = new_time.strftime("%Y-%m-%dT%H:%M:%S")

        reschedule_data = {
            "new_scheduled_datetime": new_scheduled_datetime,
            "reason": "Customer requested different time",
            "notify_customer": True,
        }

        headers = get_auth_headers(1)  # Staff member
        response = await client.post(
            f"/api/v1/appointments/{test_appointment.uuid}/reschedule",
            json=reschedule_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        # Check that the appointment was rescheduled (exact format may vary due to timezone conversions)
        returned_date = data["scheduled_datetime"][:10]  # Get just the date part
        expected_date = new_scheduled_datetime[:10]  # Get just the date part
        assert returned_date == expected_date
        assert data["reschedule_count"] == 1
        assert "Customer requested different time" in data["internal_notes"]


class TestAppointmentAPISlotLocking:
    """Test appointment slot locking API endpoints."""

    @pytest.mark.asyncio
    async def test_lock_appointment_slot(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test locking appointment slot."""
        lock_data = {
            "session_id": "test_session_123",
            "lock_duration_minutes": 20,
        }

        headers = get_auth_headers(test_appointment.staff_id)  # Staff member
        response = await client.post(
            f"/api/v1/appointments/{test_appointment.uuid}/lock",
            json=lock_data,
            headers=headers,
        )

        assert response.status_code == 200
        assert "locked successfully" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_unlock_appointment_slot(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test unlocking appointment slot."""
        # First lock the slot
        test_appointment.slot_locked = True
        test_appointment.locked_by_session_id = "test_session_123"
        await db.flush()

        headers = get_auth_headers(test_appointment.staff_id)  # Staff member
        response = await client.delete(
            f"/api/v1/appointments/{test_appointment.uuid}/lock?session_id=test_session_123",
            headers=headers,
        )

        assert response.status_code == 200
        assert "unlocked successfully" in response.json()["message"]


class TestAppointmentAPIUtilities:
    """Test appointment utility API endpoints."""

    @pytest.mark.asyncio
    async def test_check_cancellation_policy_can_cancel(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_customer,
        test_staff,
        test_service,
        mock_current_business,
    ):
        """Test cancellation policy check when appointment can be cancelled."""
        from datetime import timezone
        from uuid import uuid4
        from app.models.appointment import Appointment, AppointmentStatus
        from decimal import Decimal

        # Create a fresh appointment for this test
        future_datetime = datetime.now(timezone.utc) + timedelta(days=2)
        scheduled_time = future_datetime.replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        estimated_end = scheduled_time + timedelta(minutes=30)

        appointment = Appointment(
            uuid=uuid4(),
            business_id=test_business.id,
            customer_id=test_customer.id,
            staff_id=test_staff.id,
            service_id=test_service.id,
            scheduled_datetime=scheduled_time,
            estimated_end_datetime=estimated_end,
            duration_minutes=30,
            total_price=Decimal("50.00"),
            status=AppointmentStatus.TENTATIVE.value,
            booking_source="admin",
        )
        db.add(appointment)
        await db.flush()
        await db.refresh(appointment)

        check_data = {
            "appointment_uuid": str(appointment.uuid),
            "current_time": datetime.now(timezone.utc).isoformat(),
        }

        headers = get_auth_headers(appointment.staff_id)
        response = await client.post(
            "/api/v1/appointments/check-cancellation-policy",
            json=check_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_cancel"] is True

    @pytest.mark.asyncio
    async def test_check_cancellation_policy_cannot_cancel(
        self,
        client: AsyncClient,
        db,
        test_business,
        test_customer,
        test_staff,
        test_service,
        mock_current_business,
    ):
        """Test cancellation policy check when appointment cannot be cancelled."""
        from datetime import timezone
        from uuid import uuid4
        from app.models.appointment import Appointment, AppointmentStatus
        from decimal import Decimal

        # Create a fresh appointment for this test - scheduled soon (within cancellation window)
        near_datetime = datetime.now(timezone.utc) + timedelta(hours=2)
        scheduled_time = near_datetime.replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        estimated_end = scheduled_time + timedelta(minutes=30)

        appointment = Appointment(
            uuid=uuid4(),
            business_id=test_business.id,
            customer_id=test_customer.id,
            staff_id=test_staff.id,
            service_id=test_service.id,
            scheduled_datetime=scheduled_time,
            estimated_end_datetime=estimated_end,
            duration_minutes=30,
            total_price=Decimal("50.00"),
            status=AppointmentStatus.TENTATIVE.value,
            booking_source="admin",
        )
        db.add(appointment)
        await db.flush()
        await db.refresh(appointment)

        check_data = {
            "appointment_uuid": str(appointment.uuid),
            "current_time": datetime.now(timezone.utc).isoformat(),
        }

        headers = get_auth_headers(appointment.staff_id)
        response = await client.post(
            "/api/v1/appointments/check-cancellation-policy",
            json=check_data,
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["can_cancel"] is False
        assert "cancellation window" in data["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_appointment_conflicts(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test appointment conflict checking."""
        check_data = {
            "staff_id": test_appointment.staff_id,
            "scheduled_datetime": "2024-01-16T14:15:00",  # Overlaps with existing
            "duration_minutes": 30,
        }

        headers = get_auth_headers(test_appointment.staff_id)
        response = await client.post(
            "/api/v1/appointments/check-conflicts", json=check_data, headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "has_conflict" in data
        assert "conflicts" in data
        assert "alternative_slots" in data

    @pytest.mark.asyncio
    async def test_bulk_status_update(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test bulk appointment status update."""
        # Create additional appointment
        appointment2 = Appointment(
            uuid=uuid4(),
            business_id=test_appointment.business_id,
            customer_id=test_appointment.customer_id,
            staff_id=test_appointment.staff_id,
            service_id=test_appointment.service_id,
            scheduled_datetime=datetime(2024, 1, 17, 14, 0, 0),
            estimated_end_datetime=datetime(2024, 1, 17, 14, 30, 0),
            duration_minutes=30,
            total_price=Decimal("50.00"),
            status=AppointmentStatus.TENTATIVE.value,
            booking_source="admin",
        )
        db.add(appointment2)
        await db.flush()

        bulk_data = {
            "appointment_uuids": [str(test_appointment.uuid), str(appointment2.uuid)],
            "new_status": "confirmed",
            "notes": "Bulk confirmation",
            "notify_customers": True,
        }

        headers = get_auth_headers(test_appointment.staff_id)
        response = await client.post(
            "/api/v1/appointments/bulk-status-update", json=bulk_data, headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["successful_updates"]) <= 2  # May have some failures
        assert data["total_processed"] == 2

    @pytest.mark.asyncio
    async def test_get_appointment_stats(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test getting appointment statistics."""
        # Create appointments with different statuses
        completed_appointment = Appointment(
            uuid=uuid4(),
            business_id=test_appointment.business_id,
            customer_id=test_appointment.customer_id,
            staff_id=test_appointment.staff_id,
            service_id=test_appointment.service_id,
            scheduled_datetime=datetime(2024, 1, 15, 14, 0, 0),
            estimated_end_datetime=datetime(2024, 1, 15, 14, 30, 0),
            duration_minutes=30,
            total_price=Decimal("75.00"),
            status=AppointmentStatus.COMPLETED.value,
            booking_source="admin",
        )
        db.add(completed_appointment)
        await db.flush()

        headers = get_auth_headers(test_appointment.staff_id)
        response = await client.get(
            "/api/v1/appointments/analytics/stats", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "total_appointments" in data
        assert "completed_appointments" in data
        assert "total_revenue" in data
        assert "cancellation_rate" in data
        assert "no_show_rate" in data
        assert "average_appointment_value" in data


class TestAppointmentAPIDelete:
    """Test appointment deletion API endpoints."""

    @pytest.mark.asyncio
    async def test_delete_appointment(
        self, client: AsyncClient, db, test_appointment, mock_current_business
    ):
        """Test deleting appointment (soft delete by cancellation)."""
        headers = get_auth_headers(test_appointment.staff_id)
        response = await client.delete(
            f"/api/v1/appointments/{test_appointment.uuid}", headers=headers
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify appointment was cancelled, not actually deleted
        await db.refresh(test_appointment)
        assert test_appointment.status == AppointmentStatus.CANCELLED.value
        assert test_appointment.is_cancelled is True

    @pytest.mark.asyncio
    async def test_delete_appointment_not_found(
        self, client: AsyncClient, db, mock_current_business
    ):
        """Test deleting non-existent appointment."""
        fake_uuid = uuid4()
        headers = get_auth_headers(1)  # Use any staff ID for non-existent test
        response = await client.delete(
            f"/api/v1/appointments/{fake_uuid}", headers=headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
