import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from fastapi import status
from fastapi.testclient import TestClient
from httpx import AsyncClient
from datetime import datetime

from app.main import app
from app.models.business import Business
from app.schemas.business import (
    BusinessCreate,
    BusinessUpdate,
    BusinessBranding,
    BusinessPolicy,
)


@pytest_asyncio.fixture
async def async_client():
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.unit
class TestBusinessAPI:
    """Unit tests for Business API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

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
    def sample_business_model(self, sample_business_data):
        """Sample business model for testing."""
        business = Business(id=1, **sample_business_data, is_active=True)
        # Set datetime fields manually since they're auto-generated in real DB
        business.created_at = datetime(2024, 1, 15, 10, 30, 0)
        business.updated_at = datetime(2024, 1, 15, 10, 30, 0)
        return business

    @pytest.mark.asyncio
    async def test_create_business_success(
        self, async_client, sample_business_data, override_get_db
    ):
        """Test successful business creation."""
        with patch(
            "app.services.business.business_service.create_business"
        ) as mock_create:
            mock_business = Business(id=1, **sample_business_data, is_active=True)
            mock_business.created_at = datetime(2024, 1, 15, 10, 30, 0)
            mock_business.updated_at = datetime(2024, 1, 15, 10, 30, 0)
            mock_create.return_value = mock_business

            response = await async_client.post(
                "/api/v1/business/", json=sample_business_data
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
                "/api/v1/business/", json={"name": "Test"}
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
                "/api/v1/business/", json=sample_business_data
            )

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert response.json()["detail"] == "Failed to create business"

    @pytest.mark.asyncio
    async def test_get_business_success(
        self, async_client, sample_business_model, override_get_db
    ):
        """Test successful business retrieval."""
        with patch("app.services.business.business_service.get_business") as mock_get:
            mock_get.return_value = sample_business_model

            response = await async_client.get("/api/v1/business/1")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == 1
            assert data["name"] == "Test Salon"
            mock_get.assert_called_once_with(mock_get.call_args[0][0], 1)

    @pytest.mark.asyncio
    async def test_get_business_not_found(self, async_client, override_get_db):
        """Test business retrieval when business not found."""
        with patch("app.services.business.business_service.get_business") as mock_get:
            mock_get.return_value = None

            response = await async_client.get("/api/v1/business/999")

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
                "/api/v1/business/?skip=0&limit=10&active_only=true"
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
                "/api/v1/business/?skip=20&limit=5&active_only=false"
            )

            assert response.status_code == status.HTTP_200_OK
            mock_get_list.assert_called_once_with(
                mock_get_list.call_args[0][0], skip=20, limit=5, active_only=False
            )

    @pytest.mark.asyncio
    async def test_update_business_success(
        self, async_client, sample_business_model, override_get_db
    ):
        """Test successful business update."""
        update_data = {"name": "Updated Salon", "description": "Updated description"}
        # Create updated business properly without SQLAlchemy internal state
        updated_business = Business(
            id=sample_business_model.id,
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
            "app.services.business.business_service.update_business"
        ) as mock_update:
            mock_update.return_value = updated_business

            response = await async_client.put("/api/v1/business/1", json=update_data)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["name"] == "Updated Salon"
            assert data["description"] == "Updated description"
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_business_not_found(self, async_client, override_get_db):
        """Test business update when business not found."""
        with patch(
            "app.services.business.business_service.update_business"
        ) as mock_update:
            mock_update.return_value = None

            response = await async_client.put(
                "/api/v1/business/999", json={"name": "New Name"}
            )

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Business not found"

    @pytest.mark.asyncio
    async def test_update_business_validation_error(
        self, async_client, override_get_db
    ):
        """Test business update with validation error."""
        with patch(
            "app.services.business.business_service.update_business"
        ) as mock_update:
            mock_update.side_effect = ValueError("Invalid data")

            response = await async_client.put(
                "/api/v1/business/1", json={"name": "Test"}
            )

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Invalid data" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_business_soft_delete_success(
        self, async_client, override_get_db
    ):
        """Test successful soft delete of business."""
        with patch(
            "app.services.business.business_service.delete_business"
        ) as mock_delete:
            mock_delete.return_value = True

            response = await async_client.delete("/api/v1/business/1?hard_delete=false")

            assert response.status_code == status.HTTP_204_NO_CONTENT
            mock_delete.assert_called_once_with(
                mock_delete.call_args[0][0], 1, soft_delete=True
            )

    @pytest.mark.asyncio
    async def test_delete_business_hard_delete_success(
        self, async_client, override_get_db
    ):
        """Test successful hard delete of business."""
        with patch(
            "app.services.business.business_service.delete_business"
        ) as mock_delete:
            mock_delete.return_value = True

            response = await async_client.delete("/api/v1/business/1?hard_delete=true")

            assert response.status_code == status.HTTP_204_NO_CONTENT
            mock_delete.assert_called_once_with(
                mock_delete.call_args[0][0], 1, soft_delete=False
            )

    @pytest.mark.asyncio
    async def test_delete_business_not_found(self, async_client, override_get_db):
        """Test business deletion when business not found."""
        with patch(
            "app.services.business.business_service.delete_business"
        ) as mock_delete:
            mock_delete.return_value = False

            response = await async_client.delete("/api/v1/business/999")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Business not found"

    @pytest.mark.asyncio
    async def test_activate_business_success(
        self, async_client, sample_business_model, override_get_db
    ):
        """Test successful business activation."""
        with patch(
            "app.services.business.business_service.activate_business"
        ) as mock_activate:
            mock_activate.return_value = sample_business_model

            response = await async_client.post("/api/v1/business/1/activate")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == 1
            assert data["is_active"] is True
            mock_activate.assert_called_once_with(mock_activate.call_args[0][0], 1)

    @pytest.mark.asyncio
    async def test_activate_business_not_found(self, async_client, override_get_db):
        """Test business activation when business not found."""
        with patch(
            "app.services.business.business_service.activate_business"
        ) as mock_activate:
            mock_activate.return_value = None

            response = await async_client.post("/api/v1/business/999/activate")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert response.json()["detail"] == "Business not found"

    @pytest.mark.asyncio
    async def test_create_business_invalid_json(self, async_client, override_get_db):
        """Test business creation with invalid JSON payload."""
        response = await async_client.post("/api/v1/business/", json={})

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @pytest.mark.asyncio
    async def test_get_businesses_invalid_pagination(
        self, async_client, override_get_db
    ):
        """Test businesses listing with invalid pagination parameters."""
        response = await async_client.get("/api/v1/business/?skip=-1&limit=0")

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
            response = await async_client.get("/api/v1/business/?limit=1000")
            assert response.status_code == status.HTTP_200_OK

            # Test exceeding maximum limit
            response = await async_client.get("/api/v1/business/?limit=1001")
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
