import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.service import ServiceCategoryService
from app.schemas.service import ServiceCategoryCreate, ServiceCategoryUpdate
from app.models.business import Business
from app.models.service_category import ServiceCategory
from tests.fixtures.service_fixtures import (
    sample_business, sample_service_category, sample_child_category,
    multiple_service_categories, sample_service
)


class TestServiceCategoryService:
    """Test service category business logic."""

    async def test_get_categories_root_only(self, db: AsyncSession, multiple_service_categories: list[ServiceCategory]):
        """Test getting root categories only."""
        business_id = multiple_service_categories[0].business_id
        
        # Get root categories (no parent)
        categories = await ServiceCategoryService.get_categories(db, business_id, parent_id=None)
        
        assert len(categories) == 2  # Hair Services, Nail Services
        assert all(cat.parent_id is None for cat in categories)
        assert categories[0].name in ["Hair Services", "Nail Services"]

    async def test_get_categories_by_parent(self, db: AsyncSession, multiple_service_categories: list[ServiceCategory]):
        """Test getting categories by parent."""
        business_id = multiple_service_categories[0].business_id
        hair_category = next(cat for cat in multiple_service_categories if cat.name == "Hair Services")
        
        # Get child categories
        child_categories = await ServiceCategoryService.get_categories(db, business_id, parent_id=hair_category.id)
        
        assert len(child_categories) == 2  # Cuts, Color
        assert all(cat.parent_id == hair_category.id for cat in child_categories)
        names = [cat.name for cat in child_categories]
        assert "Cuts" in names
        assert "Color" in names

    async def test_get_category_success(self, db: AsyncSession, sample_service_category: ServiceCategory):
        """Test getting a single category successfully."""
        category = await ServiceCategoryService.get_category(
            db, sample_service_category.id, sample_service_category.business_id
        )
        
        assert category is not None
        assert category.id == sample_service_category.id
        assert category.name == sample_service_category.name

    async def test_get_category_not_found(self, db: AsyncSession, sample_business: Business):
        """Test getting a non-existent category."""
        category = await ServiceCategoryService.get_category(db, 99999, sample_business.id)
        
        assert category is None

    async def test_get_category_wrong_business(self, db: AsyncSession, sample_service_category: ServiceCategory):
        """Test getting a category from wrong business."""
        category = await ServiceCategoryService.get_category(
            db, sample_service_category.id, 99999  # Wrong business ID
        )
        
        assert category is None

    async def test_create_category_success(self, db: AsyncSession, sample_business: Business):
        """Test creating a category successfully."""
        category_data = ServiceCategoryCreate(
            business_id=sample_business.id,
            name="New Category",
            description="Test category",
            sort_order=5,
            is_active=True,
            icon="test-icon",
            color="#123456"
        )
        
        category = await ServiceCategoryService.create_category(db, category_data)
        
        assert category.id is not None
        assert category.name == "New Category"
        assert category.description == "Test category"
        assert category.business_id == sample_business.id
        assert category.sort_order == 5
        assert category.is_active is True
        assert category.icon == "test-icon"
        assert category.color == "#123456"

    async def test_create_category_with_valid_parent(self, db: AsyncSession, sample_service_category: ServiceCategory):
        """Test creating a category with valid parent."""
        category_data = ServiceCategoryCreate(
            business_id=sample_service_category.business_id,
            name="Child Category",
            parent_id=sample_service_category.id
        )
        
        category = await ServiceCategoryService.create_category(db, category_data)
        
        assert category.parent_id == sample_service_category.id
        assert category.business_id == sample_service_category.business_id

    async def test_create_category_with_invalid_parent(self, db: AsyncSession, sample_business: Business):
        """Test creating a category with invalid parent."""
        category_data = ServiceCategoryCreate(
            business_id=sample_business.id,
            name="Child Category",
            parent_id=99999  # Non-existent parent
        )
        
        with pytest.raises(HTTPException) as exc_info:
            await ServiceCategoryService.create_category(db, category_data)
        
        assert exc_info.value.status_code == 400
        assert "Parent category not found" in str(exc_info.value.detail)

    async def test_update_category_success(self, db: AsyncSession, sample_service_category: ServiceCategory):
        """Test updating a category successfully."""
        update_data = ServiceCategoryUpdate(
            name="Updated Category",
            description="Updated description",
            is_active=False
        )
        
        updated_category = await ServiceCategoryService.update_category(
            db, sample_service_category.id, sample_service_category.business_id, update_data
        )
        
        assert updated_category is not None
        assert updated_category.name == "Updated Category"
        assert updated_category.description == "Updated description"
        assert updated_category.is_active is False
        # Original values should remain
        assert updated_category.sort_order == sample_service_category.sort_order

    async def test_update_category_not_found(self, db: AsyncSession, sample_business: Business):
        """Test updating a non-existent category."""
        update_data = ServiceCategoryUpdate(name="Updated")
        
        result = await ServiceCategoryService.update_category(
            db, 99999, sample_business.id, update_data
        )
        
        assert result is None

    async def test_update_category_self_parent(self, db: AsyncSession, sample_service_category: ServiceCategory):
        """Test updating a category to be its own parent."""
        update_data = ServiceCategoryUpdate(parent_id=sample_service_category.id)
        
        with pytest.raises(HTTPException) as exc_info:
            await ServiceCategoryService.update_category(
                db, sample_service_category.id, sample_service_category.business_id, update_data
            )
        
        assert exc_info.value.status_code == 400
        assert "Category cannot be its own parent" in str(exc_info.value.detail)

    async def test_update_category_invalid_parent(self, db: AsyncSession, sample_service_category: ServiceCategory):
        """Test updating a category with invalid parent."""
        update_data = ServiceCategoryUpdate(parent_id=99999)
        
        with pytest.raises(HTTPException) as exc_info:
            await ServiceCategoryService.update_category(
                db, sample_service_category.id, sample_service_category.business_id, update_data
            )
        
        assert exc_info.value.status_code == 400
        assert "Parent category not found" in str(exc_info.value.detail)

    async def test_delete_category_success(self, db: AsyncSession, sample_service_category: ServiceCategory):
        """Test deleting a category successfully."""
        result = await ServiceCategoryService.delete_category(
            db, sample_service_category.id, sample_service_category.business_id
        )
        
        assert result is True
        
        # Verify category is deleted
        deleted_category = await ServiceCategoryService.get_category(
            db, sample_service_category.id, sample_service_category.business_id
        )
        assert deleted_category is None

    async def test_delete_category_not_found(self, db: AsyncSession, sample_business: Business):
        """Test deleting a non-existent category."""
        result = await ServiceCategoryService.delete_category(db, 99999, sample_business.id)
        
        assert result is False

    async def test_delete_category_with_children(self, db: AsyncSession, sample_child_category: ServiceCategory):
        """Test deleting a category that has children."""
        parent_id = sample_child_category.parent_id
        business_id = sample_child_category.business_id
        
        with pytest.raises(HTTPException) as exc_info:
            await ServiceCategoryService.delete_category(db, parent_id, business_id)
        
        assert exc_info.value.status_code == 400
        assert "Cannot delete category with child categories" in str(exc_info.value.detail)

    async def test_delete_category_with_services(self, db: AsyncSession, sample_service_category: ServiceCategory, sample_service):
        """Test deleting a category that has associated services."""
        # The sample_service fixture creates a service with sample_service_category
        
        with pytest.raises(HTTPException) as exc_info:
            await ServiceCategoryService.delete_category(
                db, sample_service_category.id, sample_service_category.business_id
            )
        
        assert exc_info.value.status_code == 400
        assert "Cannot delete category with associated services" in str(exc_info.value.detail)