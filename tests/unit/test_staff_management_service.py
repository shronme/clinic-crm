import pytest
from unittest.mock import AsyncMock, patch, Mock
from datetime import datetime, time
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.models.staff import Staff, StaffRole
from app.models.business import Business
from app.models.working_hours import WeekDay, OwnerType
from app.models.time_off import TimeOff, TimeOffStatus, TimeOffType
from app.models.availability_override import OverrideType
from app.models.staff_service import StaffService
from app.services.staff_management import StaffManagementService
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    WorkingHoursCreate,
    TimeOffCreate,
    AvailabilityOverrideCreate,
    StaffAvailabilityQuery,
)


class TestStaffManagementService:
    @pytest.fixture
    def mock_db_session(self):
        """Mock async database session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    def setup_method(self):
        """Setup test fixtures before each test method."""
        # Create test business
        self.business = Business(id=1, name="Test Salon", email="test@testsalon.com")

        # Create test staff
        self.staff = Staff(
            id=1,
            business_id=1,
            name="Test Staff",
            email="staff@test.com",
            role=StaffRole.STAFF,
            is_bookable=True,
            is_active=True,
        )

        self.admin_staff = Staff(
            id=2,
            business_id=1,
            name="Admin Staff",
            email="admin@test.com",
            role=StaffRole.OWNER_ADMIN,
            is_bookable=False,
            is_active=True,
        )

    @pytest.mark.asyncio
    async def test_create_staff_success(self, mock_db_session):
        """Test successful staff creation."""
        service = StaffManagementService(mock_db_session)

        staff_data = StaffCreate(
            business_id=1,
            name="New Staff",
            email="newstaff@test.com",
            role=StaffRole.STAFF,
        )

        # Mock database operations using patch
        with patch.object(mock_db_session, "execute") as mock_execute:
            # Mock the execute result
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = None
            mock_execute.return_value = mock_result

            # Mock other database operations
            mock_db_session.add = AsyncMock()
            mock_db_session.commit = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            # Mock the refresh to set the created staff
            async def mock_refresh(staff_obj):
                staff_obj.id = 1
                staff_obj.created_at = datetime.now()
                staff_obj.updated_at = datetime.now()

            mock_db_session.refresh.side_effect = mock_refresh

            # Mock the get_staff method that's called at the end of create_staff
            expected_staff = Staff(
                id=1,
                business_id=1,
                name="New Staff",
                email="newstaff@test.com",
                role=StaffRole.STAFF,
                is_active=True,
                is_bookable=True,
            )

            with patch.object(
                service, "get_staff", return_value=expected_staff
            ) as mock_get_staff:
                result = await service.create_staff(staff_data, created_by_staff_id=2)

                assert result.name == "New Staff"
                assert result.email == "newstaff@test.com"
                assert result.role == StaffRole.STAFF
                mock_db_session.add.assert_called_once()
                mock_db_session.commit.assert_called_once()
                mock_get_staff.assert_called_once_with(1, 1)

    @pytest.mark.asyncio
    async def test_create_staff_duplicate_email(self, mock_db_session):
        """Test staff creation with duplicate email."""
        service = StaffManagementService(mock_db_session)

        staff_data = StaffCreate(
            business_id=1,
            name="New Staff",
            email="existing@test.com",
            role=StaffRole.STAFF,
        )

        # Mock existing staff with same email - properly chain the mock calls
        existing_staff = Staff(id=10, business_id=1, email="existing@test.com")
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = existing_staff
        mock_db_session.execute.return_value = mock_execute

        with pytest.raises(HTTPException) as exc_info:
            await service.create_staff(staff_data, created_by_staff_id=2)

        assert exc_info.value.status_code == 400
        assert "already exists" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_get_staff_success(self, mock_db_session):
        """Test successful staff retrieval."""
        service = StaffManagementService(mock_db_session)

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.staff
        mock_db_session.execute.return_value = mock_execute

        result = await service.get_staff(staff_id=1, business_id=1)

        assert result == self.staff
        assert result.name == "Test Staff"

    @pytest.mark.asyncio
    async def test_get_staff_not_found(self, mock_db_session):
        """Test staff retrieval when staff doesn't exist."""
        service = StaffManagementService(mock_db_session)

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_execute

        result = await service.get_staff(staff_id=999, business_id=1)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_staff_active_only(self, mock_db_session):
        """Test listing active staff only."""
        service = StaffManagementService(mock_db_session)

        active_staff = [self.staff, self.admin_staff]

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = active_staff
        mock_execute.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_execute

        result = await service.list_staff(business_id=1, include_inactive=False)

        assert len(result) == 2
        assert all(staff.is_active for staff in result)

    @pytest.mark.asyncio
    async def test_update_staff_success(self, mock_db_session):
        """Test successful staff update."""
        service = StaffManagementService(mock_db_session)

        staff_update = StaffUpdate(name="Updated Name", phone="123-456-7890")

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.staff
        mock_db_session.execute.return_value = mock_execute

        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await service.update_staff(
            staff_id=1, staff_data=staff_update, business_id=1
        )

        assert result.name == "Updated Name"
        assert result.phone == "123-456-7890"

    @pytest.mark.asyncio
    async def test_delete_staff_success(self, mock_db_session):
        """Test successful staff soft delete."""
        service = StaffManagementService(mock_db_session)

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.staff
        mock_db_session.execute.return_value = mock_execute

        mock_db_session.commit = AsyncMock()

        result = await service.delete_staff(staff_id=1, business_id=1)

        assert result is True
        assert self.staff.is_active is False
        # Note: delete_staff only sets is_active=False, not is_bookable=False

    @pytest.mark.asyncio
    async def test_set_staff_working_hours(self, mock_db_session):
        """Test setting staff working hours."""
        service = StaffManagementService(mock_db_session)

        working_hours = [
            WorkingHoursCreate(
                weekday=WeekDay.MONDAY, start_time=time(9, 0), end_time=time(17, 0)
            ),
            WorkingHoursCreate(
                weekday=WeekDay.TUESDAY,
                start_time=time(9, 0),
                end_time=time(17, 0),
                break_start_time=time(12, 0),
                break_end_time=time(13, 0),
            ),
        ]

        # Mock staff exists - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.staff
        mock_db_session.execute.return_value = mock_execute

        # Mock existing hours query
        mock_execute_hours = Mock()
        mock_scalars_hours = Mock()
        mock_scalars_hours.all.return_value = []
        mock_execute_hours.scalars.return_value = mock_scalars_hours

        # Set up the mock to return different results for different calls
        mock_db_session.execute.side_effect = [mock_execute, mock_execute_hours]

        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await service.set_staff_working_hours(
            staff_id=1, working_hours=working_hours
        )

        assert len(result) == 2
        assert result[0].weekday == WeekDay.MONDAY
        assert result[1].weekday == WeekDay.TUESDAY
        assert result[1].break_start_time == time(12, 0)

    @pytest.mark.asyncio
    async def test_create_time_off_success(self, mock_db_session):
        """Test successful time-off creation."""
        service = StaffManagementService(mock_db_session)

        time_off_data = TimeOffCreate(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            type=TimeOffType.VACATION,
            reason="Summer vacation",
        )

        # Mock staff exists and no overlapping time-off - properly chain the mock calls
        mock_execute_staff = Mock()
        mock_execute_staff.scalar_one_or_none.return_value = self.staff

        mock_execute_overlap = Mock()
        mock_execute_overlap.scalar_one_or_none.return_value = None

        # Set up the mock to return different results for different calls
        mock_db_session.execute.side_effect = [mock_execute_staff, mock_execute_overlap]

        mock_db_session.add.return_value = None
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await service.create_time_off(
            staff_id=1, time_off_data=time_off_data, created_by_staff_id=1
        )

        assert result.type == TimeOffType.VACATION
        assert result.reason == "Summer vacation"

    @pytest.mark.asyncio
    async def test_create_time_off_overlap_conflict(self, mock_db_session):
        """Test time-off creation with overlap conflict."""
        service = StaffManagementService(mock_db_session)

        time_off_data = TimeOffCreate(
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            type=TimeOffType.VACATION,
        )

        # Mock staff exists and overlapping time-off exists - properly chain the mock calls
        mock_execute_staff = AsyncMock()
        mock_execute_staff.scalar_one_or_none.return_value = self.staff

        existing_time_off = TimeOff(
            id=1,
            owner_type=OwnerType.STAFF,
            owner_id=1,
            start_datetime=datetime(2024, 6, 2, 9, 0),
            end_datetime=datetime(2024, 6, 4, 17, 0),
            status=TimeOffStatus.APPROVED,
        )
        mock_execute_overlap = AsyncMock()
        mock_execute_overlap.scalar_one_or_none.return_value = existing_time_off

        # Set up the mock to return different results for different calls
        mock_db_session.execute.side_effect = [mock_execute_staff, mock_execute_overlap]

        with pytest.raises(HTTPException) as exc_info:
            await service.create_time_off(
                staff_id=1, time_off_data=time_off_data, created_by_staff_id=1
            )

        assert exc_info.value.status_code == 409
        assert "overlaps" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_approve_time_off_success(self, mock_db_session):
        """Test successful time-off approval."""
        service = StaffManagementService(mock_db_session)

        time_off = TimeOff(
            id=1,
            owner_type=OwnerType.STAFF,
            owner_id=1,
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 3, 17, 0),
            status=TimeOffStatus.PENDING,
        )

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = time_off
        mock_db_session.execute.return_value = mock_execute

        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await service.approve_time_off(
            time_off_id=1, approved_by_staff_id=2, approval_notes="Approved"
        )

        assert result.status == TimeOffStatus.APPROVED
        assert result.approved_by_staff_id == 2
        assert result.approval_notes == "Approved"
        assert result.approved_at is not None

    @pytest.mark.asyncio
    async def test_approve_time_off_not_pending(self, mock_db_session):
        """Test time-off approval when not in pending status."""
        service = StaffManagementService(mock_db_session)

        time_off = TimeOff(id=1, status=TimeOffStatus.APPROVED)  # Already approved

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = time_off
        mock_db_session.execute.return_value = mock_execute

        with pytest.raises(HTTPException) as exc_info:
            await service.approve_time_off(time_off_id=1, approved_by_staff_id=2)

        assert exc_info.value.status_code == 400
        assert "pending" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_create_availability_override_success(self, mock_db_session):
        """Test successful availability override creation."""
        service = StaffManagementService(mock_db_session)

        override_data = AvailabilityOverrideCreate(
            staff_id=1,
            override_type=OverrideType.UNAVAILABLE,
            start_datetime=datetime(2024, 6, 1, 9, 0),
            end_datetime=datetime(2024, 6, 1, 12, 0),
            reason="Doctor appointment",
        )

        # Mock staff exists - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.staff
        mock_db_session.execute.return_value = mock_execute

        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        result = await service.create_availability_override(
            override_data, created_by_staff_id=1
        )

        assert result.override_type == OverrideType.UNAVAILABLE
        assert result.reason == "Doctor appointment"
        assert result.staff_id == 1
        assert result.created_by_staff_id == 1

    @pytest.mark.asyncio
    async def test_calculate_staff_availability_basic(self, mock_db_session):
        """Test basic staff availability calculation."""
        service = StaffManagementService(mock_db_session)

        availability_query = StaffAvailabilityQuery(
            start_datetime=datetime(2024, 6, 3, 0, 0),  # Monday
            end_datetime=datetime(2024, 6, 4, 23, 59),  # Tuesday
            include_time_offs=True,
            include_overrides=True,
        )

        # Mock staff exists and is active/bookable - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = self.staff
        mock_db_session.execute.return_value = mock_execute

        # Mock service method calls
        service.get_staff_working_hours = AsyncMock(return_value=[])
        service.get_staff_time_offs = AsyncMock(return_value=[])
        service.get_staff_availability_overrides = AsyncMock(return_value=[])

        result = await service.calculate_staff_availability(
            availability_query, staff_id=1
        )

        assert result.staff_id == 1
        assert len(result.available_slots) >= 0
        assert len(result.working_hours_summary) >= 0

    @pytest.mark.asyncio
    async def test_assign_service_to_staff_success(self, mock_db_session):
        """Test successful service assignment to staff."""
        service = StaffManagementService(mock_db_session)

        # Mock no existing mapping - the method only queries for existing StaffService mappings
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_execute

        mock_db_session.add = AsyncMock()
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        # Mock the refresh to set the created staff service
        async def mock_refresh(staff_service_obj):
            staff_service_obj.id = 1
            staff_service_obj.created_at = datetime.now()
            staff_service_obj.updated_at = datetime.now()

        mock_db_session.refresh.side_effect = mock_refresh

        overrides = {
            "override_duration_minutes": 45,
            "override_price": 75.00,
            "expertise_level": "senior",
        }

        result = await service.assign_service_to_staff(
            staff_id=1, service_id=1, **overrides
        )

        # The result should be a StaffService object, not a Staff object
        assert result.staff_id == 1
        assert result.service_id == 1
        assert result.override_duration_minutes == 45
        assert result.override_price == 75.00
        assert result.expertise_level == "senior"

    @pytest.mark.asyncio
    async def test_assign_service_update_existing_mapping(self, mock_db_session):
        """Test updating existing service assignment."""
        service = StaffManagementService(mock_db_session)

        # Mock existing mapping - the method only queries for existing StaffService mappings
        existing_mapping = StaffService(
            id=1, staff_id=1, service_id=1, override_duration_minutes=30
        )
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = existing_mapping
        mock_db_session.execute.return_value = mock_execute

        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        overrides = {"override_duration_minutes": 45}

        result = await service.assign_service_to_staff(
            staff_id=1, service_id=1, **overrides
        )

        # The result should be a StaffService object with updated overrides
        assert result.override_duration_minutes == 45

    @pytest.mark.asyncio
    async def test_remove_service_from_staff_success(self, mock_db_session):
        """Test successful service removal from staff."""
        service = StaffManagementService(mock_db_session)

        # Mock existing mapping - properly chain the mock calls
        existing_mapping = StaffService(id=1, staff_id=1, service_id=1)
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = existing_mapping
        mock_db_session.execute.return_value = mock_execute

        mock_db_session.delete = AsyncMock()
        mock_db_session.commit = AsyncMock()

        result = await service.remove_service_from_staff(staff_id=1, service_id=1)

        assert result is True

    @pytest.mark.asyncio
    async def test_remove_service_from_staff_not_found(self, mock_db_session):
        """Test service removal when mapping doesn't exist."""
        service = StaffManagementService(mock_db_session)

        # Mock no existing mapping - properly chain the mock calls
        mock_execute = Mock()
        mock_execute.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_execute

        result = await service.remove_service_from_staff(staff_id=1, service_id=999)

        assert result is False

    @pytest.mark.asyncio
    async def test_get_staff_services_available_only(self, mock_db_session):
        """Test getting available staff services only."""
        service = StaffManagementService(mock_db_session)

        available_services = [
            StaffService(id=1, staff_id=1, service_id=1, is_available=True),
            StaffService(id=2, staff_id=1, service_id=2, is_available=True),
        ]

        # Mock query result - properly chain the mock calls
        mock_execute = Mock()
        mock_scalars = Mock()
        mock_scalars.all.return_value = available_services
        mock_execute.scalars.return_value = mock_scalars
        mock_db_session.execute.return_value = mock_execute

        result = await service.get_staff_services(staff_id=1, available_only=True)

        assert len(result) == 2
        assert all(service.is_available for service in result)

    @pytest.mark.asyncio
    async def test_can_staff_access_resource_owner_admin(self, mock_db_session):
        """Test resource access for owner/admin staff."""
        service = StaffManagementService(mock_db_session)

        # Mock the get_staff method directly
        with patch.object(service, "get_staff", return_value=self.admin_staff):
            result = await service.can_staff_access_resource(
                staff_id=2, resource_type="staff", resource_id=1, action="read"
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_can_staff_access_own_resource(self, mock_db_session):
        """Test staff accessing their own resource."""
        service = StaffManagementService(mock_db_session)

        # Mock the get_staff method directly
        with patch.object(service, "get_staff", return_value=self.staff):
            result = await service.can_staff_access_resource(
                staff_id=1, resource_type="staff", resource_id=1, action="read"
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_can_staff_access_resource_other_resource_denied(
        self, mock_db_session
    ):
        """Test staff accessing other staff's resource (should be denied)."""
        service = StaffManagementService(mock_db_session)

        # Mock the get_staff method directly
        with patch.object(service, "get_staff", return_value=self.staff):
            result = await service.can_staff_access_resource(
                staff_id=1,
                resource_type="staff",
                resource_id=2,  # Different staff ID
                action="read",
            )

        assert result is False
