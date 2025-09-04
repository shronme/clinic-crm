from datetime import datetime
from unittest.mock import patch

import pytest
import pytest_asyncio
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app.main import app
from app.models.business import Business
from app.models.staff import Staff
from tests.conftest import get_auth_headers


@pytest_asyncio.fixture
async def async_client():
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.unit
class TestBusinessAPI:
    """Unit tests for Business API endpoints."""

    @pytest.fixture(autouse=True)
    def mock_auth(self, mock_owner_admin_staff):
        """Auto-use fixture to mock authentication for all tests."""
        from app.api.deps.auth import get_current_staff

        # Override only get_current_staff, let require_owner_admin check the role
        app.dependency_overrides[get_current_staff] = lambda: mock_owner_admin_staff

        yield

        # Clean up overrides
        app.dependency_overrides.clear()

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def test_uuid(self):
        """Test UUID for consistent testing."""
        return "550e8400-e29b-41d4-a716-446655440000"

    @pytest.fixture
    def sample_business_data(self):
        """Sample business data for testing."""
        return {
            "name": "Test Salon",
            "description": "A test salon",
            "phone": "+1-555-123-4567",
            "email": "test@salon.com",
            "website": "https://testsalon.com",
            "address": "123 Test St",
            "timezone": "America/New_York",
            "currency": "USD",
            "branding": {
                "primary_color": "#FF0000",
                "secondary_color": "#00FF00",
                "logo_position": "center",
            },
            "policy": {
                "min_lead_time_hours": 2,
                "max_lead_time_days": 30,
                "cancellation_window_hours": 24,
                "deposit_required": True,
                "no_show_fee": 25.0,
                "late_arrival_grace_minutes": 15,
            },
        }

    @pytest.fixture
    def sample_business_model(self, sample_business_data, test_uuid):
        """Sample business model for testing."""
        business = Business(id=1, **sample_business_data, is_active=True)
        business.uuid = test_uuid
        # Set datetime fields manually since they're auto-generated in real DB
        business.created_at = datetime(2024, 1, 15, 10, 30, 0)
        business.updated_at = datetime(2024, 1, 15, 10, 30, 0)
        return business

    @pytest.fixture
    def mock_owner_admin_staff(self):
        """Mock OWNER_ADMIN staff for testing."""
        return Staff(
            id=1,
            business_id=1,
            name="Owner Admin",
            email="owner@test.com",
            role="OWNER_ADMIN",
            is_active=True,
            is_bookable=True,
        )

    @pytest.fixture
    def mock_staff_member(self):
        """Mock STAFF member for testing."""
        return Staff(
            id=2,
            business_id=1,
            name="Staff Member",
            email="staff@test.com",
            role="STAFF",
            is_active=True,
            is_bookable=True,
        )

    @pytest.mark.asyncio
    async def test_create_business_success(
        self, async_client, sample_business_data, test_uuid, override_get_db
    ):
        """Test successful business creation."""
        with patch(
            "app.services.business.business_service.create_business"
        ) as mock_create:
            # Create a proper mock business with all required fields including UUID
            mock_business = Business(id=1, **sample_business_data, is_active=True)
            mock_business.uuid = test_uuid
            mock_business.created_at = datetime(2024, 1, 15, 10, 30, 0)
            mock_business.updated_at = datetime(2024, 1, 15, 10, 30, 0)
            mock_create.return_value = mock_business

            response = await async_client.post(
                "/api/v1/business/",
                json=sample_business_data,
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "Test Salon"
            assert data["is_active"] is True
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_business_validation_error(
        self, async_client, override_get_db
    ):
        """Test business creation with validation error."""
        with patch(
            "app.services.business.business_service.create_business"
        ) as mock_create:
            mock_create.side_effect = ValueError(
                "Business with this name may already exist"
            )

            response = await async_client.post(
                "/api/v1/business/",
                json={"name": "Test"},
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert (
                "Business with this name may already exist" in response.json()["detail"]
            )

    @pytest.mark.asyncio
    async def test_create_business_server_error(
        self, async_client, sample_business_data, override_get_db
    ):
        """Test business creation with server error."""
        with patch(
            "app.services.business.business_service.create_business"
        ) as mock_create:
            mock_create.side_effect = Exception("Database error")

            response = await async_client.post(
                "/api/v1/business/",
                json=sample_business_data,
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json()["detail"] == "Failed to create business"

    @pytest.mark.asyncio
    async def test_get_business_success(
        self, async_client, sample_business_model, test_uuid, override_get_db
    ):
        """Test successful business retrieval."""
        with patch(
            "app.services.business.business_service.get_business_by_uuid"
        ) as mock_get:
            mock_get.return_value = sample_business_model

            response = await async_client.get(
                f"/api/v1/business/{test_uuid}",
                headers=get_auth_headers(1),  # Use staff ID 1, business_id will be 1
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "Test Salon"
            # Check that the mock was called with the correct arguments
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert str(call_args[0][1]) == test_uuid

    @pytest.mark.asyncio
    async def test_get_business_not_found(
        self, async_client, test_uuid, override_get_db
    ):
        """Test business retrieval when business not found."""
        with patch(
            "app.services.business.business_service.get_business_by_uuid"
        ) as mock_get:
            mock_get.return_value = None

            response = await async_client.get(
                f"/api/v1/business/{test_uuid}",
                headers=get_auth_headers(1),  # Use staff ID 1
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Business not found"

    @pytest.mark.asyncio
    async def test_get_businesses_success(
        self, async_client, sample_business_model, override_get_db
    ):
        """Test successful businesses listing."""
        with patch(
            "app.services.business.business_service.get_businesses"
        ) as mock_get_list:
            mock_get_list.return_value = [sample_business_model]

            response = await async_client.get(
                "/api/v1/business/?skip=0&limit=10&active_only=true",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert len(data) == 1
            assert data[0]["id"] == 1
            assert data[0]["name"] == "Test Salon"
            mock_get_list.assert_called_once_with(
                mock_get_list.call_args[0][0], skip=0, limit=10, active_only=True
            )

    @pytest.mark.asyncio
    async def test_get_businesses_with_pagination(self, async_client, override_get_db):
        """Test businesses listing with pagination parameters."""
        with patch(
            "app.services.business.business_service.get_businesses"
        ) as mock_get_list:
            mock_get_list.return_value = []

            response = await async_client.get(
                "/api/v1/business/?skip=20&limit=5&active_only=false",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_200_OK
            mock_get_list.assert_called_once_with(
                mock_get_list.call_args[0][0], skip=20, limit=5, active_only=False
            )

    @pytest.mark.asyncio
    async def test_update_business_success(
        self, async_client, sample_business_model, test_uuid, override_get_db
    ):
        """Test successful business update."""
        update_data = {"name": "Updated Salon", "description": "Updated description"}
        # Create updated business properly without SQLAlchemy internal state
        updated_business = Business(
            id=sample_business_model.id,
            uuid=test_uuid,
            name=update_data.get("name", sample_business_model.name),
            description=update_data.get(
                "description", sample_business_model.description
            ),
            phone=sample_business_model.phone,
            email=sample_business_model.email,
            website=sample_business_model.website,
            address=sample_business_model.address,
            timezone=sample_business_model.timezone,
            currency=sample_business_model.currency,
            branding=sample_business_model.branding,
            policy=sample_business_model.policy,
            is_active=sample_business_model.is_active,
        )
        updated_business.created_at = sample_business_model.created_at
        updated_business.updated_at = datetime(2024, 1, 15, 10, 35, 0)  # Updated time

        with patch(
            "app.services.business.business_service.update_business_by_uuid"
        ) as mock_update:
            mock_update.return_value = updated_business

            response = await async_client.put(
                f"/api/v1/business/{test_uuid}",
                json=update_data,
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == "Updated Salon"
            assert data["description"] == "Updated description"
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_business_not_found(
        self, async_client, test_uuid, override_get_db
    ):
        """Test business update when business not found."""
        with patch(
            "app.services.business.business_service.update_business_by_uuid"
        ) as mock_update:
            mock_update.return_value = None

            response = await async_client.put(
                f"/api/v1/business/{test_uuid}",
                json={"name": "New Name"},
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Business not found"

    @pytest.mark.asyncio
    async def test_update_business_validation_error(
        self, async_client, test_uuid, override_get_db
    ):
        """Test business update with validation error."""
        with patch(
            "app.services.business.business_service.update_business_by_uuid"
        ) as mock_update:
            mock_update.side_effect = ValueError("Invalid data")

            response = await async_client.put(
                f"/api/v1/business/{test_uuid}",
                json={"name": "Test"},
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid data" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_business_soft_delete_success(
        self, async_client, test_uuid, override_get_db
    ):
        """Test successful soft delete of business."""
        with patch(
            "app.services.business.business_service.delete_business_by_uuid"
        ) as mock_delete:
            mock_delete.return_value = True

            response = await async_client.delete(
                f"/api/v1/business/{test_uuid}?hard_delete=false",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_204_NO_CONTENT
            mock_delete.assert_called_once()
            call_args = mock_delete.call_args
            assert str(call_args[0][1]) == test_uuid
            assert call_args[1]["soft_delete"] is True

    @pytest.mark.asyncio
    async def test_delete_business_hard_delete_success(
        self, async_client, test_uuid, override_get_db
    ):
        """Test successful hard delete of business."""
        with patch(
            "app.services.business.business_service.delete_business_by_uuid"
        ) as mock_delete:
            mock_delete.return_value = True

            response = await async_client.delete(
                f"/api/v1/business/{test_uuid}?hard_delete=true",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_204_NO_CONTENT
            mock_delete.assert_called_once()
            call_args = mock_delete.call_args
            assert str(call_args[0][1]) == test_uuid
            assert call_args[1]["soft_delete"] is False

    @pytest.mark.asyncio
    async def test_delete_business_not_found(
        self, async_client, test_uuid, override_get_db
    ):
        """Test business deletion when business not found."""
        with patch(
            "app.services.business.business_service.delete_business_by_uuid"
        ) as mock_delete:
            mock_delete.return_value = False

            response = await async_client.delete(
                f"/api/v1/business/{test_uuid}",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Business not found"

    @pytest.mark.asyncio
    async def test_activate_business_success(
        self, async_client, sample_business_model, test_uuid, override_get_db
    ):
        """Test successful business activation."""
        with patch(
            "app.services.business.business_service.activate_business_by_uuid"
        ) as mock_activate:
            mock_activate.return_value = sample_business_model

            response = await async_client.post(
                f"/api/v1/business/{test_uuid}/activate",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == 1
            assert data["is_active"] is True
            mock_activate.assert_called_once()
            call_args = mock_activate.call_args
            assert str(call_args[0][1]) == test_uuid

    @pytest.mark.asyncio
    async def test_activate_business_not_found(
        self, async_client, test_uuid, override_get_db
    ):
        """Test business activation when business not found."""
        with patch(
            "app.services.business.business_service.activate_business_by_uuid"
        ) as mock_activate:
            mock_activate.return_value = None

            response = await async_client.post(
                f"/api/v1/business/{test_uuid}/activate",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Business not found"

    @pytest.mark.asyncio
    async def test_create_business_invalid_json(self, async_client, override_get_db):
        """Test business creation with invalid JSON payload."""
        response = await async_client.post(
            "/api/v1/business/",
            json={},
            headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_businesses_invalid_pagination(
        self, async_client, override_get_db
    ):
        """Test businesses listing with invalid pagination parameters."""
        response = await async_client.get(
            "/api/v1/business/?skip=-1&limit=0",
            headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
        )

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_businesses_pagination_limits(
        self, async_client, override_get_db
    ):
        """Test businesses listing with pagination limits."""
        with patch(
            "app.services.business.business_service.get_businesses"
        ) as mock_get_list:
            mock_get_list.return_value = []

            # Test maximum limit
            response = await async_client.get(
                "/api/v1/business/?limit=1000",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )
            assert response.status_code == status.HTTP_200_OK

            # Test exceeding maximum limit
            response = await async_client.get(
                "/api/v1/business/?limit=1001",
                headers=get_auth_headers(1),  # Use staff ID 1 for OWNER_ADMIN
            )
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_create_business_forbidden_non_owner_admin(
        self, async_client, sample_business_data, override_get_db, mock_staff_member
    ):
        """Test business creation is forbidden for non-OWNER_ADMIN users."""
        # Override only get_current_staff, let require_owner_admin check the role
        from app.api.deps.auth import get_current_staff

        app.dependency_overrides[get_current_staff] = lambda: mock_staff_member

        try:
            # Use staff ID 2 which should have STAFF role (not OWNER_ADMIN)
            response = await async_client.post(
                "/api/v1/business/",
                json=sample_business_data,
                headers=get_auth_headers(2),  # Use staff ID 2 for STAFF role
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Owner admin access required" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_get_businesses_forbidden_non_owner_admin(
        self, async_client, override_get_db, mock_staff_member
    ):
        """Test business listing is forbidden for non-OWNER_ADMIN users."""
        # Override only get_current_staff, let require_owner_admin check the role
        from app.api.deps.auth import get_current_staff

        app.dependency_overrides[get_current_staff] = lambda: mock_staff_member

        try:
            # Use staff ID 2 which should have STAFF role (not OWNER_ADMIN)
            response = await async_client.get(
                "/api/v1/business/",
                headers=get_auth_headers(2),  # Use staff ID 2 for STAFF role
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Owner admin access required" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_update_business_forbidden_non_owner_admin(
        self, async_client, test_uuid, override_get_db, mock_staff_member
    ):
        """Test business update is forbidden for non-OWNER_ADMIN users."""
        # Override only get_current_staff, let require_owner_admin check the role
        from app.api.deps.auth import get_current_staff

        app.dependency_overrides[get_current_staff] = lambda: mock_staff_member

        try:
            # Use staff ID 2 which should have STAFF role (not OWNER_ADMIN)
            response = await async_client.put(
                f"/api/v1/business/{test_uuid}",
                json={"name": "New Name"},
                headers=get_auth_headers(2),  # Use staff ID 2 for STAFF role
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Owner admin access required" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_delete_business_forbidden_non_owner_admin(
        self, async_client, test_uuid, override_get_db, mock_staff_member
    ):
        """Test business deletion is forbidden for non-OWNER_ADMIN users."""
        # Override only get_current_staff, let require_owner_admin check the role
        from app.api.deps.auth import get_current_staff

        app.dependency_overrides[get_current_staff] = lambda: mock_staff_member

        try:
            # Use staff ID 2 which should have STAFF role (not OWNER_ADMIN)
            response = await async_client.delete(
                f"/api/v1/business/{test_uuid}",
                headers=get_auth_headers(2),  # Use staff ID 2 for STAFF role
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Owner admin access required" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_activate_business_forbidden_non_owner_admin(
        self, async_client, test_uuid, override_get_db, mock_staff_member
    ):
        """Test business activation is forbidden for non-OWNER_ADMIN users."""
        # Override only get_current_staff, let require_owner_admin check the role
        from app.api.deps.auth import get_current_staff

        app.dependency_overrides[get_current_staff] = lambda: mock_staff_member

        try:
            # Use staff ID 2 which should have STAFF role (not OWNER_ADMIN)
            response = await async_client.post(
                f"/api/v1/business/{test_uuid}/activate",
                headers=get_auth_headers(2),  # Use staff ID 2 for STAFF role
            )

            assert response.status_code == status.HTTP_403_FORBIDDEN
            assert "Owner admin access required" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()
