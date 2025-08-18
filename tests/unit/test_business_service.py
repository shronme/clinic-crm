import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from services.business import BusinessService, business_service
from models.business import Business
from schemas.business import (
    BusinessCreate,
    BusinessUpdate,
    BusinessBranding,
    BusinessPolicy,
)


@pytest.mark.unit
class TestBusinessService:
    """Unit tests for BusinessService."""

    @pytest.fixture
    def service(self):
        """Create BusinessService instance."""
        return BusinessService()

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        session = AsyncMock(spec=AsyncSession)
        return session

    @pytest.fixture
    def sample_business_create(self):
        """Sample BusinessCreate schema."""
        return BusinessCreate(
            name="Test Salon",
            description="A test salon",
            phone="+1-555-123-4567",
            email="test@salon.com",
            website="https://testsalon.com",
            address="123 Test St",
            timezone="America/New_York",
            currency="USD",
            branding=BusinessBranding(
                primary_color="#FF0000",
                secondary_color="#00FF00",
                logo_position="center",
            ),
            policy=BusinessPolicy(
                min_lead_time_hours=2,
                max_lead_time_days=30,
                cancellation_window_hours=24,
                deposit_required=True,
                no_show_fee=25.0,
                late_arrival_grace_minutes=15,
            ),
        )

    @pytest.fixture
    def sample_business_model(self):
        """Sample Business model."""
        return Business(
            id=1,
            name="Test Salon",
            description="A test salon",
            phone="+1-555-123-4567",
            email="test@salon.com",
            website="https://testsalon.com",
            address="123 Test St",
            timezone="America/New_York",
            currency="USD",
            branding={
                "primary_color": "#FF0000",
                "secondary_color": "#00FF00",
                "logo_position": "center",
            },
            policy={
                "min_lead_time_hours": 2,
                "max_lead_time_days": 30,
                "cancellation_window_hours": 24,
                "deposit_required": True,
                "no_show_fee": 25.0,
                "late_arrival_grace_minutes": 15,
            },
            is_active=True,
        )

    @pytest.mark.asyncio
    async def test_create_business_success(
        self, service, mock_db_session, sample_business_create
    ):
        """Test successful business creation."""
        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        with patch("structlog.get_logger") as mock_logger:
            mock_logger.return_value.info = MagicMock()

            result = await service.create_business(
                mock_db_session, sample_business_create
            )

            assert isinstance(result, Business)
            assert result.name == "Test Salon"
            assert result.timezone == "America/New_York"
            assert result.currency == "USD"

            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()
            mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_business_with_nested_objects(self, service, mock_db_session):
        """Test business creation with nested branding and policy objects."""
        business_data = BusinessCreate(
            name="Nested Test Salon",
            branding=BusinessBranding(primary_color="#FF0000"),
            policy=BusinessPolicy(min_lead_time_hours=4),
        )

        mock_db_session.commit = AsyncMock()
        mock_db_session.refresh = AsyncMock()

        with patch("structlog.get_logger"):
            result = await service.create_business(mock_db_session, business_data)

            assert isinstance(result, Business)
            assert result.name == "Nested Test Salon"
            mock_db_session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_business_integrity_error(
        self, service, mock_db_session, sample_business_create
    ):
        """Test business creation with integrity constraint violation."""
        mock_db_session.commit.side_effect = IntegrityError(
            "constraint", "detail", "orig"
        )
        mock_db_session.rollback = AsyncMock()

        with patch("structlog.get_logger") as mock_logger:
            mock_logger.return_value.error = MagicMock()

            with pytest.raises(
                ValueError, match="Business with this name may already exist"
            ):
                await service.create_business(mock_db_session, sample_business_create)

            mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_business_general_exception(
        self, service, mock_db_session, sample_business_create
    ):
        """Test business creation with general exception."""
        mock_db_session.commit.side_effect = Exception("Database error")
        mock_db_session.rollback = AsyncMock()

        with patch("structlog.get_logger") as mock_logger:
            mock_logger.return_value.error = MagicMock()

            with pytest.raises(Exception, match="Database error"):
                await service.create_business(mock_db_session, sample_business_create)

            mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_business_success(
        self, service, mock_db_session, sample_business_model
    ):
        """Test successful business retrieval."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = sample_business_model
        mock_db_session.execute.return_value = mock_result

        result = await service.get_business(mock_db_session, 1)

        assert result == sample_business_model
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_business_not_found(self, service, mock_db_session):
        """Test business retrieval when business not found."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        with patch("services.business.logger") as mock_logger:
            result = await service.get_business(mock_db_session, 999)

            assert result is None
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_business_exception(self, service, mock_db_session):
        """Test business retrieval with exception."""
        mock_db_session.execute.side_effect = Exception("Database error")

        with patch("structlog.get_logger") as mock_logger:
            mock_logger.return_value.error = MagicMock()

            with pytest.raises(Exception, match="Database error"):
                await service.get_business(mock_db_session, 1)

    @pytest.mark.asyncio
    async def test_get_businesses_active_only(
        self, service, mock_db_session, sample_business_model
    ):
        """Test businesses retrieval with active_only filter."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_business_model]
        mock_db_session.execute.return_value = mock_result

        with patch("structlog.get_logger") as mock_logger:
            mock_logger.return_value.info = MagicMock()

            result = await service.get_businesses(
                mock_db_session, skip=0, limit=10, active_only=True
            )

            assert len(result) == 1
            assert result[0] == sample_business_model
            mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_businesses_pagination(self, service, mock_db_session):
        """Test businesses retrieval with pagination."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        with patch("structlog.get_logger") as mock_logger:
            mock_logger.return_value.info = MagicMock()

            result = await service.get_businesses(
                mock_db_session, skip=20, limit=5, active_only=False
            )

            assert len(result) == 0
            mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_businesses_exception(self, service, mock_db_session):
        """Test businesses retrieval with exception."""
        mock_db_session.execute.side_effect = Exception("Database error")

        with patch("structlog.get_logger") as mock_logger:
            mock_logger.return_value.error = MagicMock()

            with pytest.raises(Exception, match="Database error"):
                await service.get_businesses(mock_db_session)

    @pytest.mark.asyncio
    async def test_update_business_success(
        self, service, mock_db_session, sample_business_model
    ):
        """Test successful business update."""
        update_data = BusinessUpdate(
            name="Updated Salon", description="Updated description"
        )

        # Mock get_business to return existing business
        with patch.object(service, "get_business", return_value=sample_business_model):
            mock_db_session.execute = AsyncMock()
            mock_db_session.commit = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            with patch("structlog.get_logger") as mock_logger:
                mock_logger.return_value.info = MagicMock()

                result = await service.update_business(mock_db_session, 1, update_data)

                assert result == sample_business_model
                mock_db_session.execute.assert_called_once()
                mock_db_session.commit.assert_called_once()
                mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_business_not_found(self, service, mock_db_session):
        """Test business update when business not found."""
        update_data = BusinessUpdate(name="Updated Salon")

        with patch.object(service, "get_business", return_value=None):
            result = await service.update_business(mock_db_session, 999, update_data)

            assert result is None

    @pytest.mark.asyncio
    async def test_update_business_no_changes(
        self, service, mock_db_session, sample_business_model
    ):
        """Test business update with no actual changes."""
        update_data = BusinessUpdate()  # Empty update

        with patch.object(service, "get_business", return_value=sample_business_model):
            result = await service.update_business(mock_db_session, 1, update_data)

            assert result == sample_business_model
            # Should not call execute since no updates
            mock_db_session.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_business_integrity_error(
        self, service, mock_db_session, sample_business_model
    ):
        """Test business update with integrity constraint violation."""
        update_data = BusinessUpdate(name="Updated Salon")

        with patch.object(service, "get_business", return_value=sample_business_model):
            mock_db_session.execute.side_effect = IntegrityError(
                "constraint", "detail", "orig"
            )
            mock_db_session.rollback = AsyncMock()

            with patch("structlog.get_logger") as mock_logger:
                mock_logger.return_value.error = MagicMock()

                with pytest.raises(
                    ValueError, match="Update failed due to constraint violation"
                ):
                    await service.update_business(mock_db_session, 1, update_data)

                mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_business_soft_delete(
        self, service, mock_db_session, sample_business_model
    ):
        """Test soft delete of business."""
        with patch.object(service, "get_business", return_value=sample_business_model):
            mock_db_session.execute = AsyncMock()
            mock_db_session.commit = AsyncMock()

            with patch("structlog.get_logger") as mock_logger:
                mock_logger.return_value.info = MagicMock()

                result = await service.delete_business(
                    mock_db_session, 1, soft_delete=True
                )

                assert result is True
                mock_db_session.execute.assert_called_once()
                mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_business_hard_delete(
        self, service, mock_db_session, sample_business_model
    ):
        """Test hard delete of business."""
        with patch.object(service, "get_business", return_value=sample_business_model):
            mock_db_session.execute = AsyncMock()
            mock_db_session.commit = AsyncMock()

            with patch("structlog.get_logger") as mock_logger:
                mock_logger.return_value.info = MagicMock()

                result = await service.delete_business(
                    mock_db_session, 1, soft_delete=False
                )

                assert result is True
                mock_db_session.execute.assert_called_once()
                mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_business_not_found(self, service, mock_db_session):
        """Test delete business when business not found."""
        with patch.object(service, "get_business", return_value=None):
            result = await service.delete_business(mock_db_session, 999)

            assert result is False

    @pytest.mark.asyncio
    async def test_delete_business_exception(
        self, service, mock_db_session, sample_business_model
    ):
        """Test delete business with exception."""
        with patch.object(service, "get_business", return_value=sample_business_model):
            mock_db_session.execute.side_effect = Exception("Database error")
            mock_db_session.rollback = AsyncMock()

            with patch("structlog.get_logger") as mock_logger:
                mock_logger.return_value.error = MagicMock()

                with pytest.raises(Exception, match="Database error"):
                    await service.delete_business(mock_db_session, 1)

                mock_db_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_activate_business_success(self, service, mock_db_session):
        """Test successful business activation."""
        inactive_business = Business(id=1, name="Test Salon", is_active=False)

        with patch.object(service, "get_business", return_value=inactive_business):
            mock_db_session.execute = AsyncMock()
            mock_db_session.commit = AsyncMock()
            mock_db_session.refresh = AsyncMock()

            with patch("structlog.get_logger") as mock_logger:
                mock_logger.return_value.info = MagicMock()

                result = await service.activate_business(mock_db_session, 1)

                assert result == inactive_business
                mock_db_session.execute.assert_called_once()
                mock_db_session.commit.assert_called_once()
                mock_db_session.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_activate_business_already_active(
        self, service, mock_db_session, sample_business_model
    ):
        """Test activation of already active business."""
        with patch.object(service, "get_business", return_value=sample_business_model):
            with patch("services.business.logger") as mock_logger:
                result = await service.activate_business(mock_db_session, 1)

                assert result == sample_business_model
                # Should not call execute since business is already active
                mock_db_session.execute.assert_not_called()
                mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_activate_business_not_found(self, service, mock_db_session):
        """Test activation of non-existent business."""
        with patch.object(service, "get_business", return_value=None):
            result = await service.activate_business(mock_db_session, 999)

            assert result is None

    @pytest.mark.asyncio
    async def test_activate_business_exception(self, service, mock_db_session):
        """Test business activation with exception."""
        inactive_business = Business(id=1, name="Test Salon", is_active=False)

        with patch.object(service, "get_business", return_value=inactive_business):
            mock_db_session.execute.side_effect = Exception("Database error")
            mock_db_session.rollback = AsyncMock()

            with patch("structlog.get_logger") as mock_logger:
                mock_logger.return_value.error = MagicMock()

                with pytest.raises(Exception, match="Database error"):
                    await service.activate_business(mock_db_session, 1)

                mock_db_session.rollback.assert_called_once()

    def test_business_service_singleton(self):
        """Test that business_service is properly instantiated."""
        assert isinstance(business_service, BusinessService)
