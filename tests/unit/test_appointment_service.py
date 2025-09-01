from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

import pytest

from app.models.appointment import Appointment, AppointmentStatus, CancellationReason
from app.models.business import Business
from app.models.customer import Customer
from app.models.service import Service
from app.models.staff import Staff
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentFilters,
    AppointmentSearch,
    AppointmentSlotLock,
    AppointmentStatusTransition,
    AppointmentUpdate,
    BookingSourceSchema,
    BulkAppointmentStatusUpdate,
    CancellationPolicyCheck,
    ConflictCheckRequest,
)
from app.services.appointment import AppointmentService


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = AsyncMock()
    # Set up common mock patterns for database operations
    db.add = Mock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def appointment_service(mock_db):
    """Create appointment service with mocked database."""
    return AppointmentService(mock_db)


@pytest.fixture
def sample_business():
    """Sample business entity."""
    return Business(
        id=1,
        uuid=uuid4(),
        name="Test Salon",
    )


@pytest.fixture
def sample_customer():
    """Sample customer entity."""
    return Customer(
        id=1,
        uuid=uuid4(),
        business_id=1,
        first_name="John",
        last_name="Doe",
    )


@pytest.fixture
def sample_staff():
    """Sample staff entity."""
    return Staff(
        id=1,
        uuid=uuid4(),
        name="Jane Stylist",
        business_id=1,
    )


@pytest.fixture
def sample_service():
    """Sample service entity."""
    return Service(
        id=1,
        uuid=uuid4(),
        name="Haircut",
        duration_minutes=30,
        price=Decimal("50.00"),
        business_id=1,
    )


@pytest.fixture
def sample_appointment_create():
    """Sample appointment creation data."""
    return AppointmentCreate(
        business_id=1,
        customer_id=1,
        staff_id=1,
        service_id=1,
        scheduled_datetime=datetime(2024, 1, 16, 14, 0, 0),
        duration_minutes=30,
        total_price=Decimal("50.00"),
        booking_source=BookingSourceSchema.ADMIN,
    )


class TestAppointmentServiceCreate:
    """Test appointment creation functionality."""

    @pytest.mark.asyncio
    async def test_create_appointment_success(
        self,
        appointment_service: AppointmentService,
        mock_db,
        sample_appointment_create,
        sample_business,
        sample_customer,
        sample_staff,
        sample_service,
    ):
        """Test successful appointment creation."""
        # Mock entity validation - set up execute to return proper async mock results
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_business,  # Business check
            sample_customer,  # Customer check
            sample_staff,  # Staff check
            sample_service,  # Service check
        ]

        # Mock the helper methods to avoid complex async chaining
        with patch.object(
            appointment_service, "_get_customer_by_id", return_value=sample_customer
        ):
            with patch.object(
                appointment_service, "_get_staff_by_id", return_value=sample_staff
            ):
                with patch.object(
                    appointment_service,
                    "_get_service_by_id",
                    return_value=sample_service,
                ):
                    # Mock scheduling validation
                    with patch.object(
                        appointment_service.scheduling_engine, "validate_appointment"
                    ) as mock_validate:
                        mock_validate.return_value.is_valid = True
                        mock_validate.return_value.conflicts = []

                        result = await appointment_service.create_appointment(
                            sample_appointment_create
                        )

                        assert result is not None
                        assert (
                            result.customer_id == sample_appointment_create.customer_id
                        )
                        assert result.staff_id == sample_appointment_create.staff_id
                        assert result.service_id == sample_appointment_create.service_id
                        assert result.status == AppointmentStatus.TENTATIVE.value

                        mock_db.add.assert_called_once()
                        mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_appointment_validation_failure(
        self,
        appointment_service: AppointmentService,
        mock_db,
        sample_appointment_create,
        sample_business,
        sample_customer,
        sample_staff,
        sample_service,
    ):
        """Test appointment creation with validation failure."""
        # Mock entity validation
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_business,
            sample_customer,
            sample_staff,
            sample_service,
        ]

        # Mock the helper methods
        with patch.object(
            appointment_service, "_get_customer_by_id", return_value=sample_customer
        ):
            with patch.object(
                appointment_service, "_get_staff_by_id", return_value=sample_staff
            ):
                with patch.object(
                    appointment_service,
                    "_get_service_by_id",
                    return_value=sample_service,
                ):
                    # Mock scheduling validation failure
                    with patch.object(
                        appointment_service.scheduling_engine, "validate_appointment"
                    ) as mock_validate:
                        mock_validate.return_value.is_valid = False
                        mock_validate.return_value.conflicts = ["Staff unavailable"]

                        with pytest.raises(
                            ValueError, match="Appointment validation failed"
                        ):
                            await appointment_service.create_appointment(
                                sample_appointment_create
                            )

    @pytest.mark.asyncio
    async def test_create_appointment_missing_business(
        self,
        appointment_service: AppointmentService,
        mock_db,
        sample_appointment_create,
    ):
        """Test appointment creation with missing business."""
        # Mock missing business - should fail on the first check
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Business .* not found"):
            await appointment_service.create_appointment(sample_appointment_create)

    @pytest.mark.asyncio
    async def test_create_appointment_with_slot_locking(
        self,
        appointment_service: AppointmentService,
        mock_db,
        sample_appointment_create,
        sample_business,
        sample_customer,
        sample_staff,
        sample_service,
    ):
        """Test appointment creation with slot locking."""
        # Mock entity validation
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_business,
            sample_customer,
            sample_staff,
            sample_service,
        ]

        # Mock the helper methods
        with patch.object(
            appointment_service, "_get_customer_by_id", return_value=sample_customer
        ):
            with patch.object(
                appointment_service, "_get_staff_by_id", return_value=sample_staff
            ):
                with patch.object(
                    appointment_service,
                    "_get_service_by_id",
                    return_value=sample_service,
                ):
                    # Mock scheduling validation
                    with patch.object(
                        appointment_service.scheduling_engine, "validate_appointment"
                    ) as mock_validate:
                        mock_validate.return_value.is_valid = True
                        mock_validate.return_value.conflicts = []

                        session_id = "test_session_123"
                        result = await appointment_service.create_appointment(
                            sample_appointment_create, session_id=session_id
                        )

                        # Verify slot was locked
                        assert result.slot_locked
                        assert result.locked_by_session_id == session_id


class TestAppointmentServiceRead:
    """Test appointment reading functionality."""

    @pytest.mark.asyncio
    async def test_get_appointment_by_uuid_success(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test successful appointment retrieval by UUID."""
        appointment_uuid = str(uuid4())
        expected_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            customer_id=1,
            staff_id=1,
            service_id=1,
        )

        # Create a proper async mock result
        mock_result = Mock()  # Non-async mock for the result
        mock_result.scalar_one_or_none.return_value = expected_appointment
        mock_db.execute.return_value = mock_result  # execute returns this result

        result = await appointment_service.get_appointment_by_uuid(appointment_uuid)

        assert result == expected_appointment

    @pytest.mark.asyncio
    async def test_get_appointment_by_uuid_not_found(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test appointment retrieval when not found."""
        appointment_uuid = str(uuid4())

        # Create a proper async mock result
        mock_result = Mock()  # Non-async mock for the result
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        result = await appointment_service.get_appointment_by_uuid(appointment_uuid)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_appointments_with_filters(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test appointment retrieval with filters and pagination."""
        search = AppointmentSearch(
            filters=AppointmentFilters(
                business_id=1,
                status=AppointmentStatus.CONFIRMED,
            ),
            page=1,
            page_size=10,
        )

        expected_appointments = [
            Appointment(id=1, status=AppointmentStatus.CONFIRMED.value),
            Appointment(id=2, status=AppointmentStatus.CONFIRMED.value),
        ]

        # Mock query execution
        mock_db.execute.side_effect = [
            Mock(scalar=Mock(return_value=2)),  # Count query
            Mock(
                scalars=Mock(
                    return_value=Mock(all=Mock(return_value=expected_appointments))
                )
            ),  # Data query
        ]

        appointments, total_count = await appointment_service.get_appointments(
            search, 1
        )

        assert len(appointments) == 2
        assert total_count == 2


class TestAppointmentServiceUpdate:
    """Test appointment update functionality."""

    @pytest.mark.asyncio
    async def test_update_appointment_success(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test successful appointment update."""
        appointment_uuid = str(uuid4())
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            customer_id=1,
            staff_id=1,
            service_id=1,
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_datetime=datetime(2024, 1, 15, 14, 0, 0),
            duration_minutes=30,
            total_price=Decimal("50.00"),
        )

        update_data = AppointmentUpdate(
            total_price=Decimal("60.00"), customer_notes="Updated notes"
        )

        # Mock get appointment
        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            result = await appointment_service.update_appointment(
                appointment_uuid, update_data
            )

            assert result.total_price == Decimal("60.00")
            assert result.customer_notes == "Updated notes"
            mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_appointment_reschedule(
        self,
        appointment_service: AppointmentService,
        mock_db,
        sample_staff,
        sample_service,
        sample_customer,
    ):
        """Test appointment update with rescheduling."""
        appointment_uuid = str(uuid4())
        old_datetime = datetime(2024, 1, 15, 14, 0, 0)
        new_datetime = datetime(2024, 1, 16, 10, 0, 0)

        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            customer_id=1,
            staff_id=1,
            service_id=1,
            status=AppointmentStatus.CONFIRMED.value,
            scheduled_datetime=old_datetime,
            duration_minutes=30,
            reschedule_count=0,
        )

        update_data = AppointmentUpdate(scheduled_datetime=new_datetime)

        # Mock get appointment and entities
        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(
                appointment_service, "_get_staff_by_id", return_value=sample_staff
            ):
                with patch.object(
                    appointment_service,
                    "_get_service_by_id",
                    return_value=sample_service,
                ):
                    with patch.object(
                        appointment_service,
                        "_get_customer_by_id",
                        return_value=sample_customer,
                    ):
                        with patch.object(
                            appointment_service.scheduling_engine,
                            "validate_appointment",
                        ) as mock_validate:
                            mock_validate.return_value.is_valid = True
                            mock_validate.return_value.conflicts = []

                            result = await appointment_service.update_appointment(
                                appointment_uuid, update_data
                            )

                            assert result.scheduled_datetime == new_datetime
                            assert result.reschedule_count == 1
                            assert result.rescheduled_from_datetime == old_datetime

    @pytest.mark.asyncio
    async def test_update_appointment_not_found(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test appointment update when appointment not found."""
        appointment_uuid = str(uuid4())
        update_data = AppointmentUpdate(total_price=Decimal("60.00"))

        # Mock appointment not found
        with patch.object(
            appointment_service, "get_appointment_by_uuid", return_value=None
        ):
            result = await appointment_service.update_appointment(
                appointment_uuid, update_data
            )

            assert result is None


class TestAppointmentServiceStatusTransition:
    """Test appointment status transition functionality."""

    @pytest.mark.asyncio
    async def test_transition_appointment_status_success(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test successful status transition."""
        appointment_uuid = str(uuid4())
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            status=AppointmentStatus.TENTATIVE.value,
        )

        transition = AppointmentStatusTransition(new_status=AppointmentStatus.CONFIRMED)

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(
                existing_appointment, "can_transition_to", return_value=True
            ):
                with patch.object(
                    existing_appointment, "transition_to", return_value=True
                ):
                    result = await appointment_service.transition_appointment_status(
                        appointment_uuid, transition
                    )

                    assert result == existing_appointment

    @pytest.mark.asyncio
    async def test_transition_appointment_status_invalid_transition(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test invalid status transition."""
        appointment_uuid = str(uuid4())
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            status=AppointmentStatus.COMPLETED.value,
        )

        transition = AppointmentStatusTransition(new_status=AppointmentStatus.CONFIRMED)

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(
                existing_appointment, "can_transition_to", return_value=False
            ):
                with pytest.raises(ValueError, match="Cannot transition from"):
                    await appointment_service.transition_appointment_status(
                        appointment_uuid, transition
                    )

    @pytest.mark.asyncio
    async def test_transition_appointment_status_cancellation(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test appointment cancellation with policy validation."""
        appointment_uuid = str(uuid4())
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            status=AppointmentStatus.CONFIRMED.value,
        )

        transition = AppointmentStatusTransition(
            new_status=AppointmentStatus.CANCELLED,
            cancellation_reason=CancellationReason.CUSTOMER_REQUEST,
            cancellation_fee=Decimal("10.00"),
        )

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(
                existing_appointment, "can_transition_to", return_value=True
            ):
                with patch.object(
                    existing_appointment,
                    "is_cancellable",
                    return_value=(True, "Can cancel"),
                ):
                    with patch.object(
                        existing_appointment, "transition_to", return_value=True
                    ):
                        result = (
                            await appointment_service.transition_appointment_status(
                                appointment_uuid, transition, staff_id=123
                            )
                        )

                        assert result == existing_appointment
                        assert existing_appointment.cancelled_by_staff_id == 123
                        assert (
                            existing_appointment.cancellation_reason
                            == CancellationReason.CUSTOMER_REQUEST.value
                        )
                        assert existing_appointment.cancellation_fee == Decimal("10.00")


class TestAppointmentServiceSlotLocking:
    """Test appointment slot locking functionality."""

    @pytest.mark.asyncio
    async def test_lock_appointment_slot_success(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test successful slot locking."""
        appointment_uuid = str(uuid4())
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
        )

        lock_data = AppointmentSlotLock(
            session_id="test_session_123", lock_duration_minutes=20
        )

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(existing_appointment, "lock_slot", return_value=True):
                result = await appointment_service.lock_appointment_slot(
                    appointment_uuid, lock_data
                )

                assert result is True
                mock_db.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_lock_appointment_slot_failure(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test slot locking failure."""
        appointment_uuid = str(uuid4())
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
        )

        lock_data = AppointmentSlotLock(
            session_id="test_session_123", lock_duration_minutes=20
        )

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(existing_appointment, "lock_slot", return_value=False):
                result = await appointment_service.lock_appointment_slot(
                    appointment_uuid, lock_data
                )

                assert result is False
                mock_db.flush.assert_not_called()

    @pytest.mark.asyncio
    async def test_unlock_appointment_slot_success(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test successful slot unlocking."""
        appointment_uuid = str(uuid4())
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
        )

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(existing_appointment, "unlock_slot", return_value=True):
                result = await appointment_service.unlock_appointment_slot(
                    appointment_uuid, session_id="test_session_123"
                )

                assert result is True
                mock_db.flush.assert_called_once()


class TestAppointmentServicePolicyValidation:
    """Test appointment policy validation functionality."""

    @pytest.mark.asyncio
    async def test_check_cancellation_policy_can_cancel(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test cancellation policy check when appointment can be cancelled."""
        appointment_uuid = uuid4()
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            scheduled_datetime=datetime(2024, 1, 16, 14, 0, 0),
            total_price=Decimal("50.00"),
        )
        existing_appointment.service = Mock(spec=Service)  # Mock service relationship

        check = CancellationPolicyCheck(
            appointment_uuid=appointment_uuid,
            current_time=datetime(2024, 1, 15, 10, 0, 0),  # 28 hours before
        )

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(
                existing_appointment,
                "is_cancellable",
                return_value=(True, "Can cancel"),
            ):
                result = await appointment_service.check_cancellation_policy(check)

                assert result.can_cancel is True
                assert result.reason == "Can cancel"
                assert result.cancellation_fee is None  # Outside window

    @pytest.mark.asyncio
    async def test_check_cancellation_policy_cannot_cancel(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test cancellation policy check when appointment cannot be cancelled."""
        appointment_uuid = uuid4()
        existing_appointment = Appointment(
            id=1,
            uuid=appointment_uuid,
            scheduled_datetime=datetime(2024, 1, 15, 12, 0, 0),
            total_price=Decimal("50.00"),
        )
        existing_appointment.service = Mock(spec=Service)

        check = CancellationPolicyCheck(
            appointment_uuid=appointment_uuid,
            current_time=datetime(2024, 1, 15, 10, 0, 0),  # 2 hours before
        )

        with patch.object(
            appointment_service,
            "get_appointment_by_uuid",
            return_value=existing_appointment,
        ):
            with patch.object(
                existing_appointment,
                "is_cancellable",
                return_value=(False, "Within window"),
            ):
                result = await appointment_service.check_cancellation_policy(check)

                assert result.can_cancel is False
                assert result.reason == "Within window"

    @pytest.mark.asyncio
    async def test_check_appointment_conflicts_no_conflicts(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test conflict checking with no conflicts."""
        check = ConflictCheckRequest(
            staff_id=1,
            scheduled_datetime=datetime(2024, 1, 15, 14, 0, 0),
            duration_minutes=30,
        )

        # Mock no conflicting appointments with proper async chain
        mock_result = Mock()  # Non-async mock for the result
        mock_scalars = Mock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await appointment_service.check_appointment_conflicts(check)

        assert result.has_conflict is False
        assert len(result.conflicts) == 0

    @pytest.mark.asyncio
    async def test_check_appointment_conflicts_with_conflicts(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test conflict checking with conflicts found."""
        check = ConflictCheckRequest(
            staff_id=1,
            scheduled_datetime=datetime(2024, 1, 15, 14, 0, 0),
            duration_minutes=30,
        )

        conflicting_appointment = Appointment(
            id=1,
            uuid=uuid4(),
            scheduled_datetime=datetime(2024, 1, 15, 14, 15, 0),
        )

        # Mock conflicting appointments with proper async chain
        mock_result = Mock()  # Non-async mock for the result
        mock_scalars = Mock()
        mock_scalars.all.return_value = [conflicting_appointment]
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await appointment_service.check_appointment_conflicts(check)

        assert result.has_conflict is True
        assert len(result.conflicts) == 1
        assert len(result.alternative_slots) > 0  # Should suggest alternatives


class TestAppointmentServiceBulkOperations:
    """Test appointment bulk operations."""

    @pytest.mark.asyncio
    async def test_bulk_update_status_success(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test successful bulk status update."""
        appointment_uuids = [uuid4(), uuid4()]

        bulk_update = BulkAppointmentStatusUpdate(
            appointment_uuids=appointment_uuids,
            new_status=AppointmentStatus.CONFIRMED,
            notes="Bulk confirmation",
        )

        # Mock successful transitions
        with patch.object(
            appointment_service, "transition_appointment_status"
        ) as mock_transition:
            mock_transition.side_effect = [
                Appointment(id=1, uuid=appointment_uuids[0]),  # Success
                Appointment(id=2, uuid=appointment_uuids[1]),  # Success
            ]

            result = await appointment_service.bulk_update_status(bulk_update)

            assert len(result.successful_updates) == 2
            assert len(result.failed_updates) == 0
            assert result.total_processed == 2

    @pytest.mark.asyncio
    async def test_bulk_update_status_partial_failure(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test bulk status update with partial failures."""
        appointment_uuids = [uuid4(), uuid4()]

        bulk_update = BulkAppointmentStatusUpdate(
            appointment_uuids=appointment_uuids,
            new_status=AppointmentStatus.CONFIRMED,
        )

        # Mock mixed results
        with patch.object(
            appointment_service, "transition_appointment_status"
        ) as mock_transition:
            mock_transition.side_effect = [
                Appointment(id=1, uuid=appointment_uuids[0]),  # Success
                ValueError("Invalid transition"),  # Failure
            ]

            result = await appointment_service.bulk_update_status(bulk_update)

            assert len(result.successful_updates) == 1
            assert len(result.failed_updates) == 1
            assert result.total_processed == 2
            assert result.failed_updates[0]["error"] == "Invalid transition"


class TestAppointmentServiceStatistics:
    """Test appointment statistics functionality."""

    @pytest.mark.asyncio
    async def test_get_appointment_stats(
        self, appointment_service: AppointmentService, mock_db
    ):
        """Test appointment statistics calculation."""
        business_id = 1

        # Mock appointments data
        appointments = [
            Appointment(
                status=AppointmentStatus.CONFIRMED.value, total_price=Decimal("50.00")
            ),
            Appointment(
                status=AppointmentStatus.COMPLETED.value, total_price=Decimal("75.00")
            ),
            Appointment(
                status=AppointmentStatus.COMPLETED.value, total_price=Decimal("60.00")
            ),
            Appointment(
                status=AppointmentStatus.CANCELLED.value, total_price=Decimal("40.00")
            ),
            Appointment(
                status=AppointmentStatus.NO_SHOW.value, total_price=Decimal("55.00")
            ),
        ]

        # Mock database result with proper async chain
        mock_result = Mock()  # Non-async mock for the result
        mock_scalars = Mock()
        mock_scalars.all.return_value = appointments
        mock_result.scalars.return_value = mock_scalars
        mock_db.execute.return_value = mock_result

        result = await appointment_service.get_appointment_stats(business_id)

        assert result.total_appointments == 5
        assert result.confirmed_appointments == 1
        assert result.completed_appointments == 2
        assert result.cancelled_appointments == 1
        assert result.no_show_appointments == 1
        assert result.total_revenue == Decimal("135.00")  # Only completed appointments
        assert result.cancellation_rate == 0.2  # 1/5
        assert result.no_show_rate == 0.2  # 1/5
        assert result.average_appointment_value == Decimal("67.50")  # 135/2
