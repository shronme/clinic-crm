from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.main import app


@pytest.fixture
async def client():
    """Create async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


class TestServiceCategoryAPI:
    """Test service category API endpoints."""

    async def test_create_service_category(self, client: AsyncClient, sample_business):
        """Test creating a service category via API."""
        category_data = {
            "business_id": sample_business.id,
            "name": "Hair Services",
            "description": "All hair-related services",
            "sort_order": 1,
            "is_active": True,
            "icon": "scissors",
            "color": "#FF5733",
        }

        response = await client.post("/api/v1/services/categories", json=category_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Hair Services"
        assert data["business_id"] == sample_business.id
        assert data["color"] == "#FF5733"
        assert "id" in data
        assert "created_at" in data

    async def test_get_service_categories(
        self, client: AsyncClient, sample_service_category
    ):
        """Test getting service categories via API."""
        response = await client.get(
            "/api/v1/services/categories",
            params={"business_id": sample_service_category.business_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        category = next(c for c in data if c["id"] == sample_service_category.id)
        assert category["name"] == sample_service_category.name

    async def test_get_service_category(
        self, client: AsyncClient, sample_service_category
    ):
        """Test getting a single service category via API."""
        response = await client.get(
            f"/api/v1/services/categories/{sample_service_category.uuid}",
            params={"business_id": sample_service_category.business_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_service_category.id
        assert data["name"] == sample_service_category.name

    async def test_update_service_category(
        self, client: AsyncClient, sample_service_category
    ):
        """Test updating a service category via API."""
        update_data = {
            "name": "Updated Hair Services",
            "description": "Updated description",
            "is_active": False,
        }

        response = await client.put(
            f"/api/v1/services/categories/{sample_service_category.uuid}",
            params={"business_id": sample_service_category.business_id},
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Hair Services"
        assert data["description"] == "Updated description"
        assert data["is_active"] is False

    async def test_delete_service_category(self, client: AsyncClient, sample_business):
        """Test deleting a service category via API."""
        # First create a category to delete
        category_data = {
            "business_id": sample_business.id,
            "name": "Temporary Category",
        }
        create_response = await client.post(
            "/api/v1/services/categories", json=category_data
        )
        category_uuid = create_response.json()["uuid"]

        # Delete the category
        response = await client.delete(
            f"/api/v1/services/categories/{category_uuid}",
            params={"business_id": sample_business.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]


class TestServiceAPI:
    """Test service API endpoints."""

    async def test_create_service(
        self, client: AsyncClient, sample_business, sample_service_category
    ):
        """Test creating a service via API."""
        service_data = {
            "business_id": sample_business.id,
            "category_id": sample_service_category.id,
            "name": "Basic Haircut",
            "description": "Standard haircut service",
            "duration_minutes": 30,
            "price": "25.00",
            "buffer_before_minutes": 5,
            "buffer_after_minutes": 10,
            "is_active": True,
            "requires_deposit": False,
            "sort_order": 1,
        }

        response = await client.post("/api/v1/services/", json=service_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Basic Haircut"
        assert data["duration_minutes"] == 30
        assert data["price"] == "25.00"
        assert data["total_duration_minutes"] == 45  # 30 + 5 + 10

    async def test_get_services(self, client: AsyncClient, sample_service):
        """Test getting services via API."""
        response = await client.get(
            "/api/v1/services/", params={"business_id": sample_service.business_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        service = next(s for s in data if s["id"] == sample_service.id)
        assert service["name"] == sample_service.name

    async def test_get_services_filtered_by_category(
        self, client: AsyncClient, sample_service
    ):
        """Test getting services filtered by category via API."""
        response = await client.get(
            "/api/v1/services/",
            params={
                "business_id": sample_service.business_id,
                "category_id": sample_service.category_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert all(
            s["category_id"] == sample_service.category_id
            for s in data
            if s["category_id"]
        )

    async def test_get_services_active_only(self, client: AsyncClient, sample_service):
        """Test getting only active services via API."""
        response = await client.get(
            "/api/v1/services/",
            params={"business_id": sample_service.business_id, "is_active": True},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(s["is_active"] for s in data)

    async def test_get_service(self, client: AsyncClient, sample_service):
        """Test getting a single service via API."""
        response = await client.get(
            f"/api/v1/services/{sample_service.uuid}",
            params={"business_id": sample_service.business_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_service.id
        assert data["name"] == sample_service.name

    async def test_update_service(self, client: AsyncClient, sample_service):
        """Test updating a service via API."""
        update_data = {
            "name": "Premium Haircut",
            "price": "35.00",
            "duration_minutes": 45,
        }

        response = await client.put(
            f"/api/v1/services/{sample_service.uuid}",
            params={"business_id": sample_service.business_id},
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Premium Haircut"
        assert data["price"] == "35.00"
        assert data["duration_minutes"] == 45

    async def test_delete_service(
        self, client: AsyncClient, sample_business, sample_service_category
    ):
        """Test deleting a service via API."""
        # First create a service to delete
        service_data = {
            "business_id": sample_business.id,
            "category_id": sample_service_category.id,
            "name": "Temporary Service",
            "duration_minutes": 30,
            "price": "25.00",
        }
        create_response = await client.post("/api/v1/services/", json=service_data)
        service_uuid = create_response.json()["uuid"]

        # Delete the service
        response = await client.delete(
            f"/api/v1/services/{service_uuid}",
            params={"business_id": sample_business.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]


class TestServiceAddonAPI:
    """Test service add-on API endpoints."""

    async def test_create_service_addon(
        self, client: AsyncClient, sample_business, sample_service
    ):
        """Test creating a service add-on via API."""
        addon_data = {
            "business_id": sample_business.id,
            "service_id": sample_service.id,
            "name": "Hair Wash",
            "description": "Shampoo and conditioning",
            "extra_duration_minutes": 15,
            "price": "5.00",
            "is_active": True,
            "is_required": False,
            "max_quantity": 1,
        }

        response = await client.post("/api/v1/services/addons", json=addon_data)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Hair Wash"
        assert data["price"] == "5.00"
        assert data["extra_duration_minutes"] == 15

    async def test_get_service_addons(self, client: AsyncClient, sample_service_addon):
        """Test getting service add-ons via API."""
        response = await client.get(
            "/api/v1/services/addons",
            params={"business_id": sample_service_addon.business_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        addon = next(a for a in data if a["id"] == sample_service_addon.id)
        assert addon["name"] == sample_service_addon.name

    async def test_get_service_addons_by_service(
        self, client: AsyncClient, sample_service_addon
    ):
        """Test getting service add-ons filtered by service via API."""
        response = await client.get(
            "/api/v1/services/addons",
            params={
                "business_id": sample_service_addon.business_id,
                "service_id": sample_service_addon.service_id,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert all(a["service_id"] == sample_service_addon.service_id for a in data)

    async def test_update_service_addon(
        self, client: AsyncClient, sample_service_addon
    ):
        """Test updating a service add-on via API."""
        update_data = {"name": "Premium Hair Wash", "price": "8.00"}

        response = await client.put(
            f"/api/v1/services/addons/{sample_service_addon.uuid}",
            params={"business_id": sample_service_addon.business_id},
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Premium Hair Wash"
        assert data["price"] == "8.00"


class TestStaffServiceAPI:
    """Test staff-service mapping API endpoints."""

    async def test_create_staff_service(
        self, client: AsyncClient, sample_staff, sample_service
    ):
        """Test creating a staff-service mapping via API."""
        mapping_data = {
            "staff_id": sample_staff.id,
            "service_id": sample_service.id,
            "override_price": "30.00",
            "is_available": True,
            "expertise_level": "senior",
            "notes": "Specializes in modern cuts",
        }

        response = await client.post(
            "/api/v1/services/staff-services", json=mapping_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["staff_id"] == sample_staff.id
        assert data["service_id"] == sample_service.id
        assert data["override_price"] == "30.00"
        assert data["expertise_level"] == "senior"

    async def test_get_staff_services(self, client: AsyncClient, sample_staff_service):
        """Test getting staff-service mappings via API."""
        response = await client.get("/api/v1/services/staff-services")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

        mapping = next(m for m in data if m["id"] == sample_staff_service.id)
        assert mapping["staff_id"] == sample_staff_service.staff_id

    async def test_get_staff_services_by_staff(
        self, client: AsyncClient, sample_staff_service
    ):
        """Test getting staff-service mappings filtered by staff via API."""
        response = await client.get(
            "/api/v1/services/staff-services",
            params={"staff_id": sample_staff_service.staff_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(m["staff_id"] == sample_staff_service.staff_id for m in data)

    async def test_get_staff_services_by_service(
        self, client: AsyncClient, sample_staff_service
    ):
        """Test getting staff-service mappings filtered by service via API."""
        response = await client.get(
            "/api/v1/services/staff-services",
            params={"service_id": sample_staff_service.service_id},
        )

        assert response.status_code == 200
        data = response.json()
        assert all(m["service_id"] == sample_staff_service.service_id for m in data)

    async def test_update_staff_service(
        self, client: AsyncClient, sample_staff_service
    ):
        """Test updating a staff-service mapping via API."""
        update_data = {"expertise_level": "expert", "notes": "Master level expertise"}

        response = await client.put(
            f"/api/v1/services/staff-services/{sample_staff_service.uuid}",
            json=update_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["expertise_level"] == "expert"
        assert data["notes"] == "Master level expertise"


class TestServiceAPIErrorHandling:
    """Test error handling in service API endpoints."""

    async def test_get_nonexistent_service(self, client: AsyncClient):
        """Test getting a non-existent service."""
        fake_uuid = str(uuid4())
        response = await client.get(
            f"/api/v1/services/{fake_uuid}", params={"business_id": 1}
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_create_service_invalid_category(
        self, client: AsyncClient, sample_business
    ):
        """Test creating a service with invalid category."""
        service_data = {
            "business_id": sample_business.id,
            "category_id": 99999,  # Non-existent category
            "name": "Invalid Category Service",
            "duration_minutes": 30,
            "price": "25.00",
        }

        response = await client.post("/api/v1/services/", json=service_data)

        assert response.status_code == 400
        data = response.json()
        assert "Category not found" in data["detail"]

    async def test_create_service_invalid_data(
        self, client: AsyncClient, sample_business
    ):
        """Test creating a service with invalid data."""
        service_data = {
            "business_id": sample_business.id,
            "name": "Invalid Service",
            "duration_minutes": -10,  # Invalid: negative duration
            "price": "25.00",
        }

        response = await client.post("/api/v1/services/", json=service_data)

        assert response.status_code == 422  # Validation error

    async def test_delete_nonexistent_service(
        self, client: AsyncClient, sample_business
    ):
        """Test deleting a non-existent service."""
        fake_uuid = str(uuid4())
        response = await client.delete(
            f"/api/v1/services/{fake_uuid}", params={"business_id": sample_business.id}
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
