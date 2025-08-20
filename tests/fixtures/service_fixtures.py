import pytest
from decimal import Decimal
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.staff import Staff
from app.models.service import Service
from app.models.service_category import ServiceCategory
from app.models.service_addon import ServiceAddon
from app.models.staff_service import StaffService


@pytest.fixture
async def sample_business(db: AsyncSession) -> Business:
    """Create a sample business for testing."""
    business = Business(
        name="Test Salon",
        email="test@salon.com",
        phone="555-0123",
        address="123 Test St, Test City, TC 12345",
        timezone="America/New_York",
        currency="USD",
    )
    db.add(business)
    await db.commit()
    await db.refresh(business)
    return business


@pytest.fixture
async def sample_staff(db: AsyncSession, sample_business: Business) -> Staff:
    """Create a sample staff member for testing."""
    staff = Staff(business_id=sample_business.id, name="John Stylist")
    db.add(staff)
    await db.commit()
    await db.refresh(staff)
    return staff


@pytest.fixture
async def sample_service_category(
    db: AsyncSession, sample_business: Business
) -> ServiceCategory:
    """Create a sample service category for testing."""
    category = ServiceCategory(
        business_id=sample_business.id,
        name="Hair Services",
        description="All hair-related services",
        sort_order=1,
        is_active=True,
        icon="scissors",
        color="#FF5733",
    )
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@pytest.fixture
async def sample_child_category(
    db: AsyncSession,
    sample_business: Business,
    sample_service_category: ServiceCategory,
) -> ServiceCategory:
    """Create a child service category for testing."""
    child_category = ServiceCategory(
        business_id=sample_business.id,
        parent_id=sample_service_category.id,
        name="Cuts",
        description="Hair cutting services",
        sort_order=1,
        is_active=True,
    )
    db.add(child_category)
    await db.commit()
    await db.refresh(child_category)
    return child_category


@pytest.fixture
async def sample_service(
    db: AsyncSession,
    sample_business: Business,
    sample_service_category: ServiceCategory,
) -> Service:
    """Create a sample service for testing."""
    service = Service(
        business_id=sample_business.id,
        category_id=sample_service_category.id,
        name="Basic Haircut",
        description="Standard haircut service",
        duration_minutes=30,
        price=Decimal("25.00"),
        buffer_before_minutes=5,
        buffer_after_minutes=10,
        is_active=True,
        requires_deposit=False,
        sort_order=1,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@pytest.fixture
async def sample_premium_service(
    db: AsyncSession,
    sample_business: Business,
    sample_service_category: ServiceCategory,
) -> Service:
    """Create a premium service for testing."""
    service = Service(
        business_id=sample_business.id,
        category_id=sample_service_category.id,
        name="Premium Cut & Style",
        description="Premium haircut with styling",
        duration_minutes=60,
        price=Decimal("45.00"),
        buffer_before_minutes=10,
        buffer_after_minutes=15,
        is_active=True,
        requires_deposit=True,
        deposit_amount=Decimal("15.00"),
        sort_order=2,
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@pytest.fixture
async def sample_service_addon(
    db: AsyncSession, sample_business: Business, sample_service: Service
) -> ServiceAddon:
    """Create a sample service add-on for testing."""
    addon = ServiceAddon(
        business_id=sample_business.id,
        service_id=sample_service.id,
        name="Hair Wash",
        description="Shampoo and conditioning",
        extra_duration_minutes=15,
        price=Decimal("5.00"),
        is_active=True,
        is_required=False,
        max_quantity=1,
        sort_order=1,
    )
    db.add(addon)
    await db.commit()
    await db.refresh(addon)
    return addon


@pytest.fixture
async def sample_staff_service(
    db: AsyncSession, sample_staff: Staff, sample_service: Service
) -> StaffService:
    """Create a sample staff-service mapping for testing."""
    staff_service = StaffService(
        staff_id=sample_staff.id,
        service_id=sample_service.id,
        override_price=Decimal("30.00"),
        is_available=True,
        expertise_level="senior",
        notes="Specializes in modern cuts",
        requires_approval=False,
    )
    db.add(staff_service)
    await db.commit()
    await db.refresh(staff_service)
    return staff_service


@pytest.fixture
async def multiple_service_categories(
    db: AsyncSession, sample_business: Business
) -> list[ServiceCategory]:
    """Create multiple service categories for testing."""
    categories = []

    # Root categories
    hair_category = ServiceCategory(
        business_id=sample_business.id,
        name="Hair Services",
        sort_order=1,
        is_active=True,
    )
    nail_category = ServiceCategory(
        business_id=sample_business.id,
        name="Nail Services",
        sort_order=2,
        is_active=True,
    )

    db.add_all([hair_category, nail_category])
    await db.commit()
    await db.refresh(hair_category)
    await db.refresh(nail_category)
    categories.extend([hair_category, nail_category])

    # Child categories
    cuts_category = ServiceCategory(
        business_id=sample_business.id,
        parent_id=hair_category.id,
        name="Cuts",
        sort_order=1,
        is_active=True,
    )
    color_category = ServiceCategory(
        business_id=sample_business.id,
        parent_id=hair_category.id,
        name="Color",
        sort_order=2,
        is_active=True,
    )

    db.add_all([cuts_category, color_category])
    await db.commit()
    await db.refresh(cuts_category)
    await db.refresh(color_category)
    categories.extend([cuts_category, color_category])

    return categories


@pytest.fixture
async def multiple_services(
    db: AsyncSession,
    sample_business: Business,
    sample_service_category: ServiceCategory,
) -> list[Service]:
    """Create multiple services for testing."""
    services = []

    basic_cut = Service(
        business_id=sample_business.id,
        category_id=sample_service_category.id,
        name="Basic Cut",
        duration_minutes=30,
        price=Decimal("25.00"),
        is_active=True,
        sort_order=1,
    )

    premium_cut = Service(
        business_id=sample_business.id,
        category_id=sample_service_category.id,
        name="Premium Cut",
        duration_minutes=45,
        price=Decimal("35.00"),
        is_active=True,
        sort_order=2,
    )

    inactive_service = Service(
        business_id=sample_business.id,
        category_id=sample_service_category.id,
        name="Inactive Service",
        duration_minutes=60,
        price=Decimal("50.00"),
        is_active=False,
        sort_order=3,
    )

    db.add_all([basic_cut, premium_cut, inactive_service])
    await db.commit()

    for service in [basic_cut, premium_cut, inactive_service]:
        await db.refresh(service)
        services.append(service)

    return services


@pytest.fixture
async def multiple_staff_members(
    db: AsyncSession, sample_business: Business
) -> list[Staff]:
    """Create multiple staff members for testing."""
    staff_members = []

    senior_stylist = Staff(business_id=sample_business.id, name="Senior Stylist")
    junior_stylist = Staff(business_id=sample_business.id, name="Junior Stylist")
    expert_colorist = Staff(business_id=sample_business.id, name="Expert Colorist")

    db.add_all([senior_stylist, junior_stylist, expert_colorist])
    await db.commit()

    for staff in [senior_stylist, junior_stylist, expert_colorist]:
        await db.refresh(staff)
        staff_members.append(staff)

    return staff_members
