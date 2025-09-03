from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.appointment import Appointment, AppointmentStatus, CancellationReason
from app.models.business import Business
from app.models.customer import Customer
from app.models.service import Service
from app.models.staff import Staff
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentFilters,
    AppointmentReschedule,
    AppointmentSearch,
    AppointmentSlotLock,
    AppointmentStats,
    AppointmentStatusTransition,
    AppointmentUpdate,
    BulkAppointmentResponse,
    BulkAppointmentStatusUpdate,
    CancellationPolicyCheck,
    CancellationPolicyResponse,
    ConflictCheckRequest,
    ConflictCheckResponse,
)
from app.schemas.scheduling import AppointmentValidationRequest
from app.services.scheduling import SchedulingEngineService


class AppointmentService:
    """Comprehensive appointment management service with CRUD, policies, and conflict
    prevention.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.scheduling_engine = SchedulingEngineService(db)

    async def create_appointment(
        self, appointment_data: AppointmentCreate, session_id: Optional[str] = None
    ) -> Appointment:
        """Create a new appointment with validation and conflict checking."""

        # Validate entities exist
        await self._validate_entities(
            appointment_data.business_id,
            appointment_data.customer_id,
            appointment_data.staff_id,
            appointment_data.service_id,
        )

        # Get service for price and duration validation
        service = await self._get_service_by_id(appointment_data.service_id)

        # Handle addons
        addon_uuids = []
        addon_duration = 0
        addon_price = 0

        if appointment_data.addon_ids:
            addons = await self._get_addons_by_ids(
                appointment_data.addon_ids, appointment_data.business_id
            )
            addon_uuids = [str(addon.uuid) for addon in addons]
            addon_duration = sum(addon.extra_duration_minutes for addon in addons)
            addon_price = sum(float(addon.price) for addon in addons)

            # Validate addons belong to the same service
            for addon in addons:
                if addon.service_id != appointment_data.service_id:
                    raise ValueError(
                        f"Addon '{addon.name}' does not belong to the selected service"
                    )

        # Calculate total duration including addons
        total_duration = appointment_data.duration_minutes + addon_duration

        # Calculate estimated end time
        estimated_end_datetime = appointment_data.scheduled_datetime + timedelta(
            minutes=total_duration
        )

        # Validate appointment constraints
        validation_request = AppointmentValidationRequest(
            staff_uuid=str(
                (await self._get_staff_by_id(appointment_data.staff_id)).uuid
            ),
            service_uuid=str(service.uuid),
            requested_datetime=appointment_data.scheduled_datetime,
            customer_uuid=str(
                (await self._get_customer_by_id(appointment_data.customer_id)).uuid
            ),
            addon_uuids=addon_uuids,
        )

        validation_response = await self.scheduling_engine.validate_appointment(
            validation_request
        )

        if not validation_response.is_valid:
            raise ValueError(
                f"Appointment validation failed: {validation_response.conflicts}"
            )

        # Calculate total price including addons
        total_price = float(appointment_data.total_price) + addon_price

        # Create appointment
        appointment = Appointment(
            business_id=appointment_data.business_id,
            customer_id=appointment_data.customer_id,
            staff_id=appointment_data.staff_id,
            service_id=appointment_data.service_id,
            scheduled_datetime=appointment_data.scheduled_datetime,
            estimated_end_datetime=estimated_end_datetime,
            duration_minutes=total_duration,
            total_price=total_price,
            status=AppointmentStatus.TENTATIVE.value,
            booking_source=appointment_data.booking_source.value,
            booked_by_staff_id=appointment_data.booked_by_staff_id,
            deposit_required=appointment_data.deposit_required,
            deposit_amount=appointment_data.deposit_amount,
            customer_notes=appointment_data.customer_notes,
            internal_notes=appointment_data.internal_notes,
        )

        # Lock slot if session provided
        if session_id:
            appointment.lock_slot(session_id)

        self.db.add(appointment)
        await self.db.flush()

        # Create appointment-addon relationships
        if appointment_data.addon_ids:
            await self._create_appointment_addons(appointment.id, addons)

        await self.db.commit()
        await self.db.refresh(appointment)
        return appointment

    async def get_appointment_by_uuid(
        self, appointment_uuid: str
    ) -> Optional[Appointment]:
        """Get appointment by UUID with relationships."""
        query = (
            select(Appointment)
            .options(
                joinedload(Appointment.business),
                joinedload(Appointment.customer),
                joinedload(Appointment.staff),
                joinedload(Appointment.service),
                joinedload(Appointment.booked_by_staff),
                joinedload(Appointment.cancelled_by_staff),
                joinedload(Appointment.appointment_addons),
            )
            .where(Appointment.uuid == appointment_uuid)
        )

        result = await self.db.execute(query)
        return result.unique().scalar_one_or_none()

    async def get_appointments(
        self, search: AppointmentSearch, business_id: Optional[int] = None
    ) -> tuple[list[Appointment], int]:
        """Get appointments with filtering, search, and pagination."""

        query = select(Appointment).options(
            joinedload(Appointment.customer),
            joinedload(Appointment.staff),
            joinedload(Appointment.service),
        )

        # Apply business filter if provided
        if business_id:
            query = query.where(Appointment.business_id == business_id)

        # Apply filters
        query = self._apply_filters(query, search.filters)

        # Apply search
        if search.query:
            query = self._apply_search(query, search.query)

        # Count total records
        count_query = select(func.count()).select_from(query.subquery())
        total_count = (await self.db.execute(count_query)).scalar()

        # Apply sorting
        query = self._apply_sorting(query, search.sort_by, search.sort_order)

        # Apply pagination
        offset = (search.page - 1) * search.page_size
        query = query.offset(offset).limit(search.page_size)

        result = await self.db.execute(query)
        appointments = result.unique().scalars().all()

        return list(appointments), total_count

    async def update_appointment(
        self, appointment_uuid: str, update_data: AppointmentUpdate
    ) -> Optional[Appointment]:
        """Update appointment with validation."""

        appointment = await self.get_appointment_by_uuid(appointment_uuid)
        if not appointment:
            return None

        # Validate rescheduling if datetime changed
        if (
            update_data.scheduled_datetime
            and update_data.scheduled_datetime != appointment.scheduled_datetime
        ):
            # Check if appointment can be rescheduled
            if not appointment.is_active:
                raise ValueError("Cannot reschedule inactive appointment")

            # Validate new time slot
            staff = await self._get_staff_by_id(appointment.staff_id)
            service = await self._get_service_by_id(appointment.service_id)
            customer = await self._get_customer_by_id(appointment.customer_id)

            validation_request = AppointmentValidationRequest(
                staff_uuid=str(staff.uuid),
                service_uuid=str(service.uuid),
                requested_datetime=update_data.scheduled_datetime,
                customer_uuid=str(customer.uuid),
                addon_uuids=[],
            )

            validation_response = await self.scheduling_engine.validate_appointment(
                validation_request
            )

            if not validation_response.is_valid:
                raise ValueError(
                    f"Rescheduling validation failed: {validation_response.conflicts}"
                )

            # Update estimated end time
            duration = update_data.duration_minutes or appointment.duration_minutes
            appointment.estimated_end_datetime = (
                update_data.scheduled_datetime + timedelta(minutes=duration)
            )
            appointment.reschedule_count += 1
            appointment.rescheduled_from_datetime = appointment.scheduled_datetime

        # Apply updates
        for field, value in update_data.model_dump(exclude_unset=True).items():
            if hasattr(appointment, field):
                setattr(appointment, field, value)

        await self.db.flush()
        await self.db.refresh(appointment)

        return appointment

    async def transition_appointment_status(
        self,
        appointment_uuid: str,
        transition: AppointmentStatusTransition,
        staff_id: Optional[int] = None,
    ) -> Optional[Appointment]:
        """Transition appointment status with policy validation."""

        appointment = await self.get_appointment_by_uuid(appointment_uuid)
        if not appointment:
            return None

        # Check if transition is valid
        if not appointment.can_transition_to(transition.new_status):
            current_status = AppointmentStatus(appointment.status)
            raise ValueError(
                f"Cannot transition from {current_status.value} to "
                f"{transition.new_status.value}"
            )

        # Handle cancellation-specific logic
        if transition.new_status == AppointmentStatus.CANCELLED:
            can_cancel, reason = appointment.is_cancellable()
            if not can_cancel:
                raise ValueError(f"Cannot cancel appointment: {reason}")

            appointment.cancelled_by_staff_id = staff_id
            appointment.cancellation_reason = (
                transition.cancellation_reason.value
                if transition.cancellation_reason
                else None
            )
            appointment.cancellation_fee = transition.cancellation_fee

        # Handle no-show specific logic
        elif transition.new_status == AppointmentStatus.NO_SHOW:
            appointment.no_show_fee = transition.no_show_fee

        # Perform the transition
        appointment.transition_to(transition.new_status, transition.notes)

        await self.db.flush()
        await self.db.refresh(appointment)

        return appointment

    async def reschedule_appointment(
        self, appointment_uuid: str, reschedule_data: AppointmentReschedule
    ) -> Optional[Appointment]:
        """Reschedule appointment to new datetime."""

        appointment = await self.get_appointment_by_uuid(appointment_uuid)
        if not appointment:
            return None

        if not appointment.is_active:
            raise ValueError("Cannot reschedule inactive appointment")

        # Create update data for rescheduling
        update_data = AppointmentUpdate(
            scheduled_datetime=reschedule_data.new_scheduled_datetime,
            internal_notes=(
                f"{appointment.internal_notes or ''}\n"
                f"Rescheduled: {reschedule_data.reason or 'No reason provided'}"
            ).strip(),
        )

        return await self.update_appointment(appointment_uuid, update_data)

    async def lock_appointment_slot(
        self, appointment_uuid: str, lock_data: AppointmentSlotLock
    ) -> bool:
        """Lock appointment slot to prevent conflicts."""

        appointment = await self.get_appointment_by_uuid(appointment_uuid)
        if not appointment:
            return False

        success = appointment.lock_slot(
            lock_data.session_id, lock_data.lock_duration_minutes
        )

        if success:
            await self.db.flush()

        return success

    async def unlock_appointment_slot(
        self, appointment_uuid: str, session_id: Optional[str] = None
    ) -> bool:
        """Unlock appointment slot."""

        appointment = await self.get_appointment_by_uuid(appointment_uuid)
        if not appointment:
            return False

        success = appointment.unlock_slot(session_id)

        if success:
            await self.db.flush()

        return success

    async def delete_appointment(self, appointment_uuid: str) -> bool:
        """Delete appointment (soft delete by cancelling)."""

        appointment = await self.get_appointment_by_uuid(appointment_uuid)
        if not appointment:
            return False

        # Cancel the appointment instead of hard delete
        transition = AppointmentStatusTransition(
            new_status=AppointmentStatus.CANCELLED,
            cancellation_reason=CancellationReason.OTHER,
            notes="Appointment deleted",
        )

        await self.transition_appointment_status(appointment_uuid, transition)
        return True

    async def check_cancellation_policy(
        self, check: CancellationPolicyCheck
    ) -> CancellationPolicyResponse:
        """Check if appointment can be cancelled based on policy."""

        appointment = await self.get_appointment_by_uuid(str(check.appointment_uuid))
        if not appointment:
            return CancellationPolicyResponse(
                can_cancel=False, reason="Appointment not found"
            )

        can_cancel, reason = appointment.is_cancellable(check.current_time)

        # Calculate cancellation fee and window end time
        cancellation_fee = None
        cancellation_window_ends_at = None

        if appointment.service:
            # This would typically come from business policy
            cancellation_window_hours = 24  # Default
            cancellation_window_ends_at = appointment.scheduled_datetime - timedelta(
                hours=cancellation_window_hours
            )

            # Apply cancellation fee if within policy window
            current_time = check.current_time or datetime.utcnow()
            if current_time > cancellation_window_ends_at and can_cancel:
                cancellation_fee = appointment.total_price * Decimal("0.5")  # 50% fee

        return CancellationPolicyResponse(
            can_cancel=can_cancel,
            reason=reason,
            cancellation_fee=cancellation_fee,
            cancellation_window_ends_at=cancellation_window_ends_at,
        )

    async def check_appointment_conflicts(
        self, check: ConflictCheckRequest
    ) -> ConflictCheckResponse:
        """Check for appointment conflicts."""

        # Query overlapping appointments
        query = select(Appointment).where(
            and_(
                Appointment.staff_id == check.staff_id,
                Appointment.is_cancelled is False,
                or_(
                    and_(
                        Appointment.scheduled_datetime <= check.scheduled_datetime,
                        Appointment.estimated_end_datetime > check.scheduled_datetime,
                    ),
                    and_(
                        Appointment.scheduled_datetime
                        < check.scheduled_datetime
                        + timedelta(minutes=check.duration_minutes),
                        Appointment.estimated_end_datetime
                        >= check.scheduled_datetime
                        + timedelta(minutes=check.duration_minutes),
                    ),
                    and_(
                        Appointment.scheduled_datetime >= check.scheduled_datetime,
                        Appointment.estimated_end_datetime
                        <= check.scheduled_datetime
                        + timedelta(minutes=check.duration_minutes),
                    ),
                ),
            )
        )

        if check.exclude_appointment_id:
            query = query.where(Appointment.id != check.exclude_appointment_id)

        result = await self.db.execute(query)
        conflicting_appointments = result.scalars().all()

        has_conflict = len(conflicting_appointments) > 0
        conflicts = [
            f"Conflict with appointment {apt.uuid} at {apt.scheduled_datetime}"
            for apt in conflicting_appointments
        ]

        # Find alternative slots (simplified)
        alternative_slots = []
        if has_conflict:
            # Look for slots within 7 days
            base_time = check.scheduled_datetime.replace(
                hour=9, minute=0, second=0, microsecond=0
            )
            for day_offset in range(7):
                for hour_offset in range(9):  # 9 AM to 5 PM
                    alternative_time = base_time + timedelta(
                        days=day_offset, hours=hour_offset
                    )
                    if alternative_time != check.scheduled_datetime:
                        # Quick check if this slot is free (simplified)
                        ConflictCheckRequest(
                            staff_id=check.staff_id,
                            scheduled_datetime=alternative_time,
                            duration_minutes=check.duration_minutes,
                            exclude_appointment_id=check.exclude_appointment_id,
                        )
                        # Recursive check would be expensive, so we'll add logic later
                        alternative_slots.append(alternative_time)
                        if len(alternative_slots) >= 5:  # Limit alternatives
                            break
                if len(alternative_slots) >= 5:
                    break

        return ConflictCheckResponse(
            has_conflict=has_conflict,
            conflicts=conflicts,
            alternative_slots=alternative_slots,
        )

    async def bulk_update_status(
        self, bulk_update: BulkAppointmentStatusUpdate
    ) -> BulkAppointmentResponse:
        """Bulk update appointment statuses."""

        successful_updates = []
        failed_updates = []

        for appointment_uuid in bulk_update.appointment_uuids:
            try:
                transition = AppointmentStatusTransition(
                    new_status=bulk_update.new_status, notes=bulk_update.notes
                )

                updated_appointment = await self.transition_appointment_status(
                    str(appointment_uuid), transition
                )

                if updated_appointment:
                    successful_updates.append(appointment_uuid)
                else:
                    failed_updates.append(
                        {"uuid": appointment_uuid, "error": "Appointment not found"}
                    )

            except Exception as e:
                failed_updates.append({"uuid": appointment_uuid, "error": str(e)})

        return BulkAppointmentResponse(
            successful_updates=successful_updates,
            failed_updates=failed_updates,
            total_processed=len(bulk_update.appointment_uuids),
        )

    async def get_appointment_stats(
        self,
        business_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> AppointmentStats:
        """Get appointment statistics for a business."""

        query = select(Appointment).where(Appointment.business_id == business_id)

        if start_date:
            query = query.where(Appointment.scheduled_datetime >= start_date)
        if end_date:
            query = query.where(Appointment.scheduled_datetime <= end_date)

        result = await self.db.execute(query)
        appointments = result.scalars().all()

        total_appointments = len(appointments)
        confirmed_appointments = sum(
            1 for apt in appointments if apt.status == AppointmentStatus.CONFIRMED.value
        )
        completed_appointments = sum(
            1 for apt in appointments if apt.status == AppointmentStatus.COMPLETED.value
        )
        cancelled_appointments = sum(
            1 for apt in appointments if apt.status == AppointmentStatus.CANCELLED.value
        )
        no_show_appointments = sum(
            1 for apt in appointments if apt.status == AppointmentStatus.NO_SHOW.value
        )

        total_revenue = sum(
            apt.total_price
            for apt in appointments
            if apt.status == AppointmentStatus.COMPLETED.value
        )

        cancellation_rate = (
            cancelled_appointments / total_appointments if total_appointments > 0 else 0
        )
        no_show_rate = (
            no_show_appointments / total_appointments if total_appointments > 0 else 0
        )
        average_appointment_value = (
            total_revenue / completed_appointments
            if completed_appointments > 0
            else Decimal("0")
        )

        return AppointmentStats(
            total_appointments=total_appointments,
            confirmed_appointments=confirmed_appointments,
            completed_appointments=completed_appointments,
            cancelled_appointments=cancelled_appointments,
            no_show_appointments=no_show_appointments,
            total_revenue=total_revenue,
            cancellation_rate=round(cancellation_rate, 4),
            no_show_rate=round(no_show_rate, 4),
            average_appointment_value=average_appointment_value,
        )

    # Helper methods
    async def _validate_entities(
        self, business_id: int, customer_id: int, staff_id: int, service_id: int
    ) -> None:
        """Validate that all required entities exist."""

        # Check business exists
        business = await self.db.execute(
            select(Business).where(Business.id == business_id)
        )
        if not business.scalar_one_or_none():
            raise ValueError(f"Business {business_id} not found")

        # Check customer exists
        customer = await self.db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        if not customer.scalar_one_or_none():
            raise ValueError(f"Customer {customer_id} not found")

        # Check staff exists and belongs to business
        staff = await self.db.execute(
            select(Staff).where(
                and_(Staff.id == staff_id, Staff.business_id == business_id)
            )
        )
        if not staff.scalar_one_or_none():
            raise ValueError(
                f"Staff {staff_id} not found or doesn't belong to business "
                f"{business_id}"
            )

        # Check service exists and belongs to business
        service = await self.db.execute(
            select(Service).where(
                and_(Service.id == service_id, Service.business_id == business_id)
            )
        )
        if not service.scalar_one_or_none():
            raise ValueError(
                f"Service {service_id} not found or doesn't belong to business "
                f"{business_id}"
            )

    async def _get_customer_by_id(self, customer_id: int) -> Customer:
        """Get customer by ID."""
        result = await self.db.execute(
            select(Customer).where(Customer.id == customer_id)
        )
        return result.scalar_one()

    async def _get_staff_by_id(self, staff_id: int) -> Staff:
        """Get staff by ID."""
        result = await self.db.execute(select(Staff).where(Staff.id == staff_id))
        return result.scalar_one()

    async def _get_service_by_id(self, service_id: int) -> Service:
        """Get service by ID."""
        result = await self.db.execute(select(Service).where(Service.id == service_id))
        return result.scalar_one()

    def _apply_filters(self, query, filters: AppointmentFilters):
        """Apply filters to appointment query."""

        if filters.business_id:
            query = query.where(Appointment.business_id == filters.business_id)
        if filters.customer_id:
            query = query.where(Appointment.customer_id == filters.customer_id)
        if filters.staff_id:
            query = query.where(Appointment.staff_id == filters.staff_id)
        if filters.service_id:
            query = query.where(Appointment.service_id == filters.service_id)
        if filters.status:
            query = query.where(Appointment.status == filters.status.value)
        if filters.start_date:
            query = query.where(Appointment.scheduled_datetime >= filters.start_date)
        if filters.end_date:
            query = query.where(Appointment.scheduled_datetime <= filters.end_date)
        if filters.booking_source:
            query = query.where(
                Appointment.booking_source == filters.booking_source.value
            )
        if filters.is_cancelled is not None:
            query = query.where(Appointment.is_cancelled == filters.is_cancelled)
        if filters.is_no_show is not None:
            query = query.where(Appointment.is_no_show == filters.is_no_show)
        if filters.deposit_paid is not None:
            query = query.where(Appointment.deposit_paid == filters.deposit_paid)

        return query

    def _apply_search(self, query, search_query: str):
        """Apply search to appointment query."""
        search_term = f"%{search_query.lower()}%"

        # Join with related tables for search - specify explicit join conditions
        query = query.join(Customer, Appointment.customer_id == Customer.id)
        query = query.join(Staff, Appointment.staff_id == Staff.id)
        query = query.join(Service, Appointment.service_id == Service.id)

        # Search in customer name (first_name + last_name), staff name, service name
        query = query.where(
            or_(
                func.lower(
                    func.concat(Customer.first_name, " ", Customer.last_name)
                ).like(search_term),
                func.lower(Customer.first_name).like(search_term),
                func.lower(Customer.last_name).like(search_term),
                func.lower(Staff.name).like(search_term),
                func.lower(Service.name).like(search_term),
            )
        )

        return query

    def _apply_sorting(self, query, sort_by: str, sort_order: str):
        """Apply sorting to appointment query."""

        sort_column = getattr(Appointment, sort_by, Appointment.scheduled_datetime)

        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        return query

    async def _get_addons_by_ids(self, addon_ids: list[int], business_id: int) -> list:
        """Get service addons by their IDs."""
        from sqlalchemy import and_

        from app.models.service_addon import ServiceAddon

        if not addon_ids:
            return []

        result = await self.db.execute(
            select(ServiceAddon).where(
                and_(
                    ServiceAddon.id.in_(addon_ids),
                    ServiceAddon.business_id == business_id,
                    ServiceAddon.is_active,
                )
            )
        )
        return result.scalars().all()

    async def _create_appointment_addons(self, appointment_id: int, addons: list):
        """Create appointment-addon relationships."""
        from app.models.appointment_addon import AppointmentAddon

        for addon in addons:
            appointment_addon = AppointmentAddon(
                appointment_id=appointment_id,
                addon_id=addon.id,
                addon_name=addon.name,
                addon_price=addon.price,
                addon_duration_minutes=addon.extra_duration_minutes,
                quantity=1,  # Default quantity, can be extended later
            )
            self.db.add(appointment_addon)
