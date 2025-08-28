import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.main import app
from app.models.staff import Staff, StaffRole
from app.models.business import Business
from app.models.service import Service


class TestStaffAPI:
    """Integration tests for Staff API endpoints."""

    @pytest.fixture
    async def client(self):
        """Async test client for the FastAPI application."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    @pytest.fixture
    async def test_business(self, db: AsyncSession):
        """Create a test business."""
        business = Business(
            id=1,
            name="Test Salon",
            email="test@testsalon.com",
            phone="123-456-7890",
            timezone="America/New_York",
            currency="USD",
            is_active=True,
        )
        db.add(business)
        await db.commit()
        await db.refresh(business)
        return business

    @pytest.fixture
    async def test_staff(self, db: AsyncSession, test_business):
        """Create a test staff member."""
        staff = Staff(
            id=1,
            uuid=uuid.uuid4(),
            business_id=test_business.id,
            name="Test Staff",
            email="staff@test.com",
            role=StaffRole.STAFF.value,
            is_bookable=True,
            is_active=True,
        )
        db.add(staff)
        await db.commit()
        await db.refresh(staff)
        return staff

    @pytest.fixture
    async def admin_staff(self, db: AsyncSession, test_business):
        """Create an admin staff member."""
        admin = Staff(
            id=2,
            uuid=uuid.uuid4(),
            business_id=test_business.id,
            name="Admin Staff",
            email="admin@test.com",
            role=StaffRole.OWNER_ADMIN.value,
            is_bookable=False,
            is_active=True,
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
        return admin

    @pytest.fixture
    async def test_service(self, db: AsyncSession, test_business):
        """Create a test service."""
        service = Service(
            id=1,
            uuid=uuid.uuid4(),
            business_id=test_business.id,
            name="Haircut",
            description="Basic haircut service",
            duration_minutes=30,
            price=25.00,
            buffer_before_minutes=5,
            buffer_after_minutes=5,
            is_active=True,
        )
        db.add(service)
        await db.commit()
        await db.refresh(service)
        return service

    @pytest.fixture
    async def other_staff(self, db: AsyncSession, test_business):
        """Create another staff member for permission testing."""
        other_staff = Staff(
            id=3,
            uuid=uuid.uuid4(),
            business_id=test_business.id,
            name="Other Staff",
            email="other@test.com",
            role=StaffRole.STAFF.value,
            is_active=True,
        )
        db.add(other_staff)
        await db.commit()
        await db.refresh(other_staff)
        return other_staff

    @pytest.mark.asyncio
    async def test_get_staff_list(
        self, client: AsyncClient, test_business, test_staff, admin_staff
    ):
        """Test getting the list of staff members."""
        headers = {
            "X-Staff-ID": "2",  # Admin staff
            "X-Business-ID": str(test_business.id),
        }

        response = await client.get("/api/v1/staff/", headers=headers)
        assert response.status_code == 200

        staff_list = response.json()
        assert len(staff_list) == 2
        assert any(staff["name"] == "Test Staff" for staff in staff_list)
        assert any(staff["name"] == "Admin Staff" for staff in staff_list)

    @pytest.mark.asyncio
    async def test_create_staff(self, client: AsyncClient, test_business, admin_staff):
        """Test creating a new staff member."""
        headers = {
            "X-Staff-ID": "2",  # Admin staff
            "X-Business-ID": str(test_business.id),
        }

        staff_data = {
            "business_id": test_business.id,
            "name": "New Staff Member",
            "email": "newstaff@test.com",
            "role": "STAFF",
            "is_bookable": True,
            "is_active": True,
        }

        response = await client.post("/api/v1/staff/", json=staff_data, headers=headers)
        assert response.status_code == 201

        created_staff = response.json()
        assert created_staff["name"] == "New Staff Member"
        assert created_staff["email"] == "newstaff@test.com"
        assert created_staff["role"] == "STAFF"

    @pytest.mark.asyncio
    async def test_get_staff_by_id(
        self, client: AsyncClient, test_business, test_staff
    ):
        """Test getting a specific staff member by UUID."""
        headers = {
            "X-Staff-ID": "1",  # Same staff member
            "X-Business-ID": str(test_business.id),
        }

        response = await client.get(f"/api/v1/staff/{test_staff.uuid}", headers=headers)
        assert response.status_code == 200

        staff = response.json()
        assert staff["id"] == test_staff.id
        assert staff["name"] == "Test Staff"
        assert staff["email"] == "staff@test.com"

    @pytest.mark.asyncio
    async def test_update_staff(self, client: AsyncClient, test_business, test_staff):
        """Test updating a staff member."""
        headers = {
            "X-Staff-ID": "1",  # Same staff member
            "X-Business-ID": str(test_business.id),
        }

        update_data = {"name": "Updated Staff Name", "phone": "987-654-3210"}

        response = await client.put(
            f"/api/v1/staff/{test_staff.uuid}", json=update_data, headers=headers
        )
        assert response.status_code == 200

        updated_staff = response.json()
        assert updated_staff["name"] == "Updated Staff Name"
        assert updated_staff["phone"] == "987-654-3210"

    @pytest.mark.asyncio
    async def test_set_staff_working_hours(
        self, client: AsyncClient, test_business, test_staff
    ):
        """Test setting working hours for a staff member."""
        headers = {
            "X-Staff-ID": "1",  # Same staff member
            "X-Business-ID": str(test_business.id),
        }

        working_hours_data = [
            {
                "weekday": 0,  # Monday
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "is_active": True,
            },
            {
                "weekday": 1,  # Tuesday
                "start_time": "09:00:00",
                "end_time": "17:00:00",
                "break_start_time": "12:00:00",
                "break_end_time": "13:00:00",
                "is_active": True,
            },
        ]

        response = await client.post(
            f"/api/v1/staff/{test_staff.uuid}/working-hours",
            json=working_hours_data,
            headers=headers,
        )
        assert response.status_code == 200

        hours = response.json()
        assert len(hours) == 2
        assert hours[0]["weekday"] == 0  # Monday
        assert hours[1]["weekday"] == 1  # Tuesday

    @pytest.mark.asyncio
    async def test_get_staff_working_hours(
        self, client: AsyncClient, test_business, test_staff
    ):
        """Test getting working hours for a staff member."""
        headers = {
            "X-Staff-ID": "1",  # Same staff member
            "X-Business-ID": str(test_business.id),
        }

        response = await client.get(
            f"/api/v1/staff/{test_staff.uuid}/working-hours", headers=headers
        )
        assert response.status_code == 200

        # Should return empty list if no hours set yet
        hours = response.json()
        assert isinstance(hours, list)

    @pytest.mark.asyncio
    async def test_create_time_off(
        self, client: AsyncClient, test_business, test_staff
    ):
        """Test creating a time-off request."""
        headers = {
            "X-Staff-ID": "1",  # Same staff member
            "X-Business-ID": str(test_business.id),
        }

        time_off_data = {
            "start_datetime": "2024-06-01T09:00:00+00:00",
            "end_datetime": "2024-06-03T17:00:00+00:00",
            "type": "VACATION",
            "reason": "Summer vacation",
            "is_all_day": False,
        }

        response = await client.post(
            f"/api/v1/staff/{test_staff.uuid}/time-off",
            json=time_off_data,
            headers=headers,
        )
        assert response.status_code == 201

        time_off = response.json()
        assert time_off["type"] == "VACATION"
        assert time_off["reason"] == "Summer vacation"

    @pytest.mark.asyncio
    async def test_approve_time_off(
        self, client: AsyncClient, test_business, test_staff, admin_staff
    ):
        """Test approving a time-off request."""
        # First create a time-off request
        headers = {
            "X-Staff-ID": "1",  # Regular staff
            "X-Business-ID": str(test_business.id),
        }

        time_off_data = {
            "start_datetime": "2024-06-01T09:00:00+00:00",
            "end_datetime": "2024-06-03T17:00:00+00:00",
            "type": "VACATION",
            "reason": "Summer vacation",
        }

        create_response = await client.post(
            f"/api/v1/staff/{test_staff.uuid}/time-off",
            json=time_off_data,
            headers=headers,
        )
        assert create_response.status_code == 201

        time_off = create_response.json()
        time_off_uuid = time_off["uuid"]  # Use UUID instead of ID

        # Now approve it as admin
        admin_headers = {
            "X-Staff-ID": "2",  # Admin staff
            "X-Business-ID": str(test_business.id),
        }

        approve_response = await client.post(
            f"/api/v1/staff/time-off/{time_off_uuid}/approve",
            json={"approval_notes": "Approved"},
            headers=admin_headers,
        )
        assert approve_response.status_code == 200

        approved_time_off = approve_response.json()
        assert approved_time_off["status"] == "APPROVED"

    @pytest.mark.asyncio
    async def test_assign_service_to_staff(
        self, client: AsyncClient, test_business, test_staff, admin_staff, test_service
    ):
        """Test assigning a service to a staff member."""
        headers = {
            "X-Staff-ID": "2",  # Admin staff
            "X-Business-ID": str(test_business.id),
        }

        service_override = {
            "service_id": str(test_service.uuid),  # Schema expects UUID
            "override_duration_minutes": 45,
            "override_price": 30.00,
            "expertise_level": "senior",
        }

        response = await client.post(
            f"/api/v1/staff/{test_staff.uuid}/services",
            json=service_override,
            headers=headers,
        )

        assert response.status_code == 200

        result = response.json()
        assert result["message"] == "Service assigned successfully"
        assert result["staff_id"] == test_staff.id
        assert result["service_id"] == test_service.id

    @pytest.mark.asyncio
    async def test_get_staff_services(
        self, client: AsyncClient, test_business, test_staff
    ):
        """Test getting services assigned to a staff member."""
        headers = {
            "X-Staff-ID": "1",  # Same staff member
            "X-Business-ID": str(test_business.id),
        }

        response = await client.get(
            f"/api/v1/staff/{test_staff.uuid}/services", headers=headers
        )
        assert response.status_code == 200

        services = response.json()
        assert isinstance(services, list)

    @pytest.mark.asyncio
    async def test_calculate_staff_availability(
        self, client: AsyncClient, test_business, test_staff
    ):
        """Test calculating staff availability."""
        headers = {
            "X-Staff-ID": "1",  # Same staff member
            "X-Business-ID": str(test_business.id),
        }

        availability_query = {
            "start_datetime": "2024-06-03T00:00:00",
            "end_datetime": "2024-06-04T23:59:59",
            "include_time_offs": True,
            "include_overrides": True,
        }

        response = await client.post(
            f"/api/v1/staff/{test_staff.uuid}/availability",
            json=availability_query,
            headers=headers,
        )
        assert response.status_code == 200

        availability = response.json()
        assert availability["staff_id"] == test_staff.id
        assert "available_slots" in availability
        assert "unavailable_periods" in availability
        assert "working_hours_summary" in availability

    @pytest.mark.asyncio
    async def test_permission_denied_for_unauthorized_access(
        self, client: AsyncClient, test_business, test_staff, other_staff
    ):
        """Test that unauthorized access is properly denied."""
        # Try to access another staff member's profile
        headers = {
            "X-Staff-ID": "1",  # Regular staff
            "X-Business-ID": str(test_business.id),
        }

        # Try to view other staff's profile (should be denied)
        response = await client.get(
            f"/api/v1/staff/{other_staff.uuid}", headers=headers
        )
        assert response.status_code == 403
        detail = response.json()["detail"]
        assert "Can only view your own staff profile" in detail

    @pytest.mark.asyncio
    async def test_business_context_validation(self, client: AsyncClient, test_staff):
        """Test that business context validation works."""
        # Non-existent business
        headers = {"X-Staff-ID": "1", "X-Business-ID": "999"}

        response = await client.get(f"/api/v1/staff/{test_staff.uuid}", headers=headers)
        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "Business not found" in detail

    @pytest.mark.asyncio
    async def test_staff_creation_duplicate_email(
        self, client: AsyncClient, test_business, admin_staff, test_staff
    ):
        """Test that creating staff with duplicate email is rejected."""
        headers = {
            "X-Staff-ID": "2",  # Admin staff
            "X-Business-ID": str(test_business.id),
        }

        duplicate_staff_data = {
            "business_id": test_business.id,
            "name": "Duplicate Staff",
            "email": "staff@test.com",  # Same email as existing staff
            "role": "STAFF",
        }

        response = await client.post(
            "/api/v1/staff/", json=duplicate_staff_data, headers=headers
        )
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]
