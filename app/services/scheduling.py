from datetime import datetime, timedelta, timezone, date as date_type, time
from typing import Any, Optional
import logging

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.availability_override import AvailabilityOverride
from app.services.holidays import HolidayService
from app.models.business import Business
from app.models.service import Service
from app.models.staff import Staff
from app.models.time_off import TimeOff, TimeOffStatus
from app.models.working_hours import OwnerType, WeekDay, WorkingHours
from app.schemas.scheduling import (
    AppointmentValidationRequest,
    AppointmentValidationResponse,
    AvailabilitySlot,
    AvailabilityStatus,
    BusinessHoursQuery,
    ConflictType,
    SchedulingConflict,
    StaffAvailabilityQuery,
    StaffScheduleQuery,
)


logger = logging.getLogger(__name__)


class SchedulingEngineService:
    """Core scheduling engine for barber & beautician CRM."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_day_has_availability(
        self, staff_uuid: str, date: date_type, service_uuid: str = None
    ) -> bool:
        """
        Check if a specific day has any available slots for a staff member.

        Args:
            staff_uuid: UUID of the staff member
            date: Date to check
            service_uuid: Optional service UUID to filter by

        Returns:
            True if the day has at least one available slot, False otherwise
        """
        logger.info(f"Checking if day {date} has availability for staff {staff_uuid}")

        # Get staff and service info
        staff = await self._get_staff_by_uuid(staff_uuid)
        if not staff:
            logger.warning(f"Staff not found: {staff_uuid}")
            return False

        service = None
        if service_uuid:
            service = await self._get_service_by_uuid(service_uuid)
            if not service:
                logger.warning(f"Service not found: {service_uuid}")
                return False

        # Create start and end datetime for the day
        start_datetime = datetime.combine(date, time.min).replace(tzinfo=timezone.utc)
        end_datetime = datetime.combine(date, time.max).replace(tzinfo=timezone.utc)

        logger.debug(f"Checking availability for {start_datetime} to {end_datetime}")

        # Check if there's at least one available slot during the day
        current_time = start_datetime
        slot_duration = timedelta(minutes=30)  # Default 30-minute slots

        if service:
            slot_duration = timedelta(minutes=service.duration_minutes)

        # We only need to find ONE available slot, so we can exit early
        while current_time < end_datetime:
            slot_end = current_time + slot_duration
            if slot_end > end_datetime:
                break

            # Check if this slot is available
            is_available, _ = await self._check_slot_availability(
                staff, current_time, slot_end, service
            )

            if is_available == AvailabilityStatus.AVAILABLE:
                logger.info(f"Found available slot at {current_time} on {date}")
                return True

            # Move to next slot
            current_time += slot_duration

        logger.info(f"No available slots found for {date}")
        return False

    async def get_available_days(
        self,
        staff_uuid: str,
        start_date: date_type,
        end_date: date_type,
        service_uuid: str = None,
    ) -> list[date_type]:
        """
        Get all days within a date range that have at least one available slot.

        Args:
            staff_uuid: UUID of the staff member
            start_date: Start date of the range (inclusive)
            end_date: End date of the range (inclusive)
            service_uuid: Optional service UUID to filter by

        Returns:
            List of dates that have availability
        """
        logger.info(
            f"Getting available days for staff {staff_uuid} from {start_date} to {end_date}"
        )

        available_days = []
        current_date = start_date

        while current_date <= end_date:
            has_availability = await self.check_day_has_availability(
                staff_uuid, current_date, service_uuid
            )

            if has_availability:
                available_days.append(current_date)
                logger.debug(f"Day {current_date} has availability")

            # Move to next day
            current_date += timedelta(days=1)

        logger.info(
            f"Found {len(available_days)} available days out of {(end_date - start_date).days + 1} total days"
        )
        return available_days

    async def get_staff_availability(
        self, query: StaffAvailabilityQuery
    ) -> list[AvailabilitySlot]:
        """Get available time slots for a staff member."""
        logger.info(
            f"Starting availability check for staff {query.staff_uuid} "
            f"from {query.start_datetime} to {query.end_datetime} "
            f"with slot duration {query.slot_duration_minutes} minutes"
        )
        # Step 1: Get staff member
        logger.debug(f"Looking up staff member with UUID: {query.staff_uuid}")
        staff = await self._get_staff_by_uuid(query.staff_uuid)
        if not staff:
            logger.warning(f"Staff member not found with UUID: {query.staff_uuid}")
            return []
        logger.info(
            f"Found staff member: {staff.name} (ID: {staff.id}, Business ID: {staff.business_id})"
        )

        # Step 2: Get service if specified
        service = None
        if query.service_uuid:
            logger.debug(f"Looking up service with UUID: {query.service_uuid}")
            service = await self._get_service_by_uuid(query.service_uuid)
            if not service:
                logger.warning(f"Service not found with UUID: {query.service_uuid}")
                return []
            logger.info(
                f"Found service: {service.name} "
                f"(Duration: {service.total_duration_minutes} minutes)"
            )
        else:
            logger.debug(
                "No specific service requested - checking general availability"
            )

        # Step 3: Generate time slots
        logger.info("Starting slot generation process")
        slots = []
        current_time = query.start_datetime
        slot_duration = timedelta(minutes=query.slot_duration_minutes)
        total_slots_checked = 0
        available_slots = 0
        busy_slots = 0
        logger.info(f"Current time: {current_time}")
        logger.info(f"Query end time: {query.end_datetime}")
        logger.info(f"Slot duration: {slot_duration}")
        logger.info(
            f"Loop condition: {current_time} < {query.end_datetime} = {current_time < query.end_datetime}"
        )

        while current_time < query.end_datetime:
            logger.info(f"ENTERING LOOP - Iteration {total_slots_checked + 1}")
            slot_end = current_time + slot_duration
            total_slots_checked += 1

            # Check if this slot can accommodate the service
            if service:
                service_end = current_time + timedelta(
                    minutes=service.total_duration_minutes
                )
                if service_end > query.end_datetime:
                    logger.debug(
                        "Service duration extends beyond query end time, "
                        "stopping slot generation"
                    )
                    break

            logger.info(
                f"Checking availability for slot {total_slots_checked}: "
                f"{current_time} - {slot_end}"
            )
            availability_status, conflicts = await self._check_slot_availability(
                staff, current_time, slot_end, service
            )
            if availability_status == AvailabilityStatus.AVAILABLE:
                available_slots += 1
                logger.debug(f"Slot {total_slots_checked} is AVAILABLE")
            else:
                busy_slots += 1
                logger.warning(
                    f"Slot {total_slots_checked} is UNAVAILABLE - "
                    f"conflicts: {[c.value for c in conflicts]} - "
                    f"Time: {current_time} - {slot_end}"
                )

            if (
                query.include_busy_slots
                or availability_status == AvailabilityStatus.AVAILABLE
            ):
                slot = AvailabilitySlot(
                    start_datetime=current_time,
                    end_datetime=slot_end,
                    status=availability_status,
                    staff_uuid=query.staff_uuid,
                    service_uuid=query.service_uuid,
                    conflicts=conflicts,
                    metadata={
                        "checked_at": datetime.utcnow().replace(tzinfo=timezone.utc)
                    },
                )
                slots.append(slot)

            current_time += slot_duration

        logger.info(
            f"Availability check completed: {total_slots_checked} total slots "
            f"checked, {available_slots} available, {busy_slots} busy, "
            f"{len(slots)} slots returned"
        )

        # If all slots are busy, log some diagnostic info
        if available_slots == 0 and total_slots_checked > 0:
            logger.error(
                f"ALL SLOTS ARE UNAVAILABLE! This suggests a configuration issue. "
                f"Staff ID: {staff.id}, Business ID: {staff.business_id}, "
                f"Service: {service.name if service else 'None'}"
            )
        return slots

    async def validate_appointment(
        self, request: AppointmentValidationRequest
    ) -> AppointmentValidationResponse:
        """Validate if an appointment can be scheduled at the requested time."""
        staff = await self._get_staff_by_uuid(request.staff_uuid)
        service = await self._get_service_by_uuid(request.service_uuid)

        if not staff or not service:
            return AppointmentValidationResponse(
                is_valid=False,
                conflicts=[
                    SchedulingConflict(
                        conflict_type=ConflictType.STAFF_UNAVAILABLE,
                        message="Staff or service not found",
                        start_datetime=request.requested_datetime,
                        end_datetime=request.requested_datetime,
                    )
                ],
                alternative_slots=[],
                total_duration_minutes=0,
                estimated_end_time=request.requested_datetime,
            )

        # Calculate total duration including addons
        total_duration = service.total_duration_minutes
        addon_duration = await self._calculate_addon_duration(request.addon_uuids)
        total_duration += addon_duration

        estimated_end_time = request.requested_datetime + timedelta(
            minutes=total_duration
        )

        # Check all scheduling constraints
        conflicts = await self._validate_scheduling_constraints(
            staff, service, request.requested_datetime, estimated_end_time
        )

        is_valid = len(conflicts) == 0

        # Generate alternative slots if not valid
        alternative_slots = []
        if not is_valid:
            alternative_slots = await self._find_alternative_slots(
                staff, service, request.requested_datetime, total_duration
            )

        return AppointmentValidationResponse(
            is_valid=is_valid,
            conflicts=conflicts,
            alternative_slots=alternative_slots,
            total_duration_minutes=total_duration,
            estimated_end_time=estimated_end_time,
        )

    async def _check_slot_availability(
        self,
        staff: Staff,
        start_time: datetime,
        end_time: datetime,
        service: Optional[Service] = None,
    ) -> tuple[AvailabilityStatus, list[ConflictType]]:
        """Check if a time slot is available for a staff member."""
        logger.debug(
            f"Checking slot availability for staff {staff.id} "
            f"from {start_time} to {end_time}"
        )

        # Use the existing comprehensive validation method
        if service:
            logger.debug(
                f"Performing comprehensive validation with service: {service.name}"
            )
            scheduling_conflicts = await self._validate_scheduling_constraints(
                staff, service, start_time, end_time
            )
            conflicts = [conflict.conflict_type for conflict in scheduling_conflicts]
            logger.debug(
                f"Comprehensive validation found {len(conflicts)} conflicts: "
                f"{[c.value for c in conflicts]}"
            )
        else:
            # For slots without a specific service, do basic availability checks
            logger.debug("Performing basic availability checks (no specific service)")
            conflicts = []

            # Check business working hours
            logger.debug(
                f"Checking business working hours for business {staff.business_id}"
            )
            business_hours_ok = await self._is_within_business_hours(
                staff.business_id, start_time, end_time
            )
            if not business_hours_ok:
                conflicts.append(ConflictType.OUTSIDE_WORKING_HOURS)
                logger.debug("Slot conflicts with business working hours")
            else:
                logger.debug("Slot is within business working hours")

            # Check staff working hours
            logger.debug(f"Checking staff working hours for staff {staff.id}")
            staff_hours_ok = await self._is_within_staff_working_hours(
                staff.id, start_time, end_time
            )
            if not staff_hours_ok:
                conflicts.append(ConflictType.OUTSIDE_WORKING_HOURS)
                logger.debug("Slot conflicts with staff working hours")
            else:
                logger.debug("Slot is within staff working hours")

            # Check for time off conflicts
            logger.debug(f"Checking for time off conflicts for staff {staff.id}")
            has_time_off = await self._has_time_off_conflict(
                staff.id, start_time, end_time
            )
            if has_time_off:
                conflicts.append(ConflictType.TIME_OFF)
                logger.debug("Slot conflicts with approved time off")
            else:
                logger.debug("No time off conflicts found")

            # Check availability overrides
            logger.debug(f"Checking availability overrides for staff {staff.id}")
            override_effect = await self._check_availability_overrides(
                staff.id, start_time, end_time
            )
            if override_effect == "unavailable":
                conflicts.append(ConflictType.AVAILABILITY_OVERRIDE)
                logger.debug("Slot is unavailable due to availability override")
            else:
                logger.debug(f"Availability override effect: {override_effect}")

            # Check for existing appointment conflicts
            logger.debug(
                f"Checking for existing appointment conflicts for staff {staff.id}"
            )
            has_appointment_conflict = await self._has_appointment_conflict(
                staff.id, start_time, end_time
            )
            if has_appointment_conflict:
                conflicts.append(ConflictType.EXISTING_APPOINTMENT)
                logger.debug("Slot conflicts with existing appointment")
            else:
                logger.debug("No existing appointment conflicts found")

        # Determine status
        if conflicts:
            logger.debug(f"Slot is UNAVAILABLE due to {len(conflicts)} conflicts")
            return AvailabilityStatus.UNAVAILABLE, conflicts
        else:
            logger.debug("Slot is AVAILABLE")
            return AvailabilityStatus.AVAILABLE, []

    async def _validate_scheduling_constraints(
        self, staff: Staff, service: Service, start_time: datetime, end_time: datetime
    ) -> list[SchedulingConflict]:
        """Validate all scheduling constraints for an appointment."""
        logger.debug(
            f"Starting comprehensive validation for staff {staff.id} and service {service.name}"
        )
        conflicts = []

        # Business hours validation
        logger.debug(f"Validating business hours for business {staff.business_id}")
        business_hours_ok = await self._is_within_business_hours(
            staff.business_id, start_time, end_time
        )
        if not business_hours_ok:
            logger.debug("Business hours validation failed")
            conflicts.append(
                SchedulingConflict(
                    conflict_type=ConflictType.OUTSIDE_WORKING_HOURS,
                    message="Appointment time is outside business hours",
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )
        else:
            logger.debug("Business hours validation passed")

        # Staff working hours validation
        logger.debug(f"Validating staff working hours for staff {staff.id}")
        staff_hours_ok = await self._is_within_staff_working_hours(
            staff.id, start_time, end_time
        )
        if not staff_hours_ok:
            logger.debug("Staff working hours validation failed")
            conflicts.append(
                SchedulingConflict(
                    conflict_type=ConflictType.OUTSIDE_WORKING_HOURS,
                    message="Appointment time is outside staff working hours",
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )
        else:
            logger.debug("Staff working hours validation passed")

        # Time off validation
        logger.debug(f"Validating time off for staff {staff.id}")
        has_time_off = await self._has_time_off_conflict(staff.id, start_time, end_time)
        if has_time_off:
            logger.debug("Time off validation failed - staff has approved time off")
            conflicts.append(
                SchedulingConflict(
                    conflict_type=ConflictType.TIME_OFF,
                    message="Staff has approved time off during this period",
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )
        else:
            logger.debug("Time off validation passed")

        # Availability override validation
        logger.debug(f"Validating availability overrides for staff {staff.id}")
        override_effect = await self._check_availability_overrides(
            staff.id, start_time, end_time
        )
        if override_effect == "unavailable":
            logger.debug("Availability override validation failed - staff unavailable")
            conflicts.append(
                SchedulingConflict(
                    conflict_type=ConflictType.AVAILABILITY_OVERRIDE,
                    message="Staff is not available due to availability override",
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )
        else:
            logger.debug(
                f"Availability override validation passed (effect: {override_effect})"
            )

        # Existing appointment validation
        logger.debug(f"Validating existing appointments for staff {staff.id}")
        has_appointment_conflict = await self._has_appointment_conflict(
            staff.id, start_time, end_time
        )
        if has_appointment_conflict:
            logger.debug("Existing appointment validation failed - conflict found")
            conflicts.append(
                SchedulingConflict(
                    conflict_type=ConflictType.EXISTING_APPOINTMENT,
                    message="Staff has existing appointment during this time",
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )
        else:
            logger.debug("Existing appointment validation passed")

        # Lead time policy validation
        logger.debug(f"Validating lead time policy for business {staff.business_id}")
        lead_time_ok = await self._check_lead_time_policy(
            staff.business_id, service, start_time
        )
        if not lead_time_ok:
            logger.debug("Lead time policy validation failed")
            conflicts.append(
                SchedulingConflict(
                    conflict_type=ConflictType.LEAD_TIME_VIOLATION,
                    message="Appointment does not meet minimum lead time requirements",
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )
        else:
            logger.debug("Lead time policy validation passed")

        # Advance booking policy validation
        logger.debug(
            f"Validating advance booking policy for business {staff.business_id}"
        )
        advance_booking_ok = await self._check_advance_booking_policy(
            staff.business_id, service, start_time
        )
        if not advance_booking_ok:
            logger.debug("Advance booking policy validation failed")
            conflicts.append(
                SchedulingConflict(
                    conflict_type=ConflictType.ADVANCE_BOOKING_VIOLATION,
                    message="Appointment exceeds maximum advance booking period",
                    start_datetime=start_time,
                    end_datetime=end_time,
                )
            )
        else:
            logger.debug("Advance booking policy validation passed")

        logger.debug(
            f"Comprehensive validation completed with {len(conflicts)} conflicts found"
        )
        return conflicts

    async def _is_within_business_hours(
        self, business_id: int, start_time: datetime, end_time: datetime
    ) -> bool:
        """Check if time period is within business hours."""
        # Holiday check: if the date is a holiday in Israel, treat as closed
        if HolidayService.is_holiday(start_time) or HolidayService.is_holiday(end_time):
            logger.debug(
                f"Date {start_time.date()} or {end_time.date()} is a holiday in Israel; business considered closed"
            )
            return False
        # Get business working hours for the day
        weekday = WeekDay(start_time.weekday())
        logger.debug(
            f"Checking business hours for business {business_id} on {weekday.name} (weekday={weekday.value})"
        )

        query = select(WorkingHours).where(
            and_(
                WorkingHours.owner_type == OwnerType.BUSINESS.value,
                WorkingHours.owner_id == business_id,
                WorkingHours.weekday == str(weekday.value),
                WorkingHours.is_active,
            )
        )
        result = await self.db.execute(query)
        business_hours = result.scalar_one_or_none()

        if not business_hours:
            logger.warning(
                f"No business hours found for business {business_id} on {weekday.name} - "
                f"this will make ALL slots unavailable!"
            )
            return False

        logger.debug(
            f"Found business hours: {business_hours.start_time} - {business_hours.end_time}"
        )

        # Apply pre-holiday cutoff at 15:00 local time (Asia/Jerusalem)
        cutoff_utc = HolidayService.get_pre_holiday_cutoff_utc(start_time)
        if cutoff_utc is not None:
            # If the slot extends beyond cutoff, it is outside business hours
            if end_time > cutoff_utc:
                return False

        # Check if time period is within working hours
        start_available = business_hours.is_time_available(start_time)
        end_available = business_hours.is_time_available(end_time)
        logger.debug(
            f"Time availability check: start={start_available}, end={end_available}"
        )

        return start_available and end_available

    async def _is_within_staff_working_hours(
        self, staff_id: int, start_time: datetime, end_time: datetime
    ) -> bool:
        """Check if time period is within staff working hours."""
        weekday = WeekDay(start_time.weekday())
        logger.debug(
            f"Checking staff working hours for staff {staff_id} on {weekday.name} (weekday={weekday.value})"
        )

        query = select(WorkingHours).where(
            and_(
                WorkingHours.owner_type == OwnerType.STAFF.value,
                WorkingHours.owner_id == staff_id,
                WorkingHours.weekday == str(weekday.value),
                WorkingHours.is_active,
            )
        )
        result = await self.db.execute(query)
        staff_hours = result.scalar_one_or_none()

        if not staff_hours:
            logger.warning(
                f"No staff working hours found for staff {staff_id} on {weekday.name} - "
                f"this will make ALL slots unavailable!"
            )
            return False

        logger.debug(
            f"Found staff working hours: {staff_hours.start_time} - {staff_hours.end_time}"
        )

        start_available = staff_hours.is_time_available(start_time)
        end_available = staff_hours.is_time_available(end_time)
        logger.debug(
            f"Staff time availability check: start={start_available}, end={end_available}"
        )

        return start_available and end_available

    async def _has_time_off_conflict(
        self, staff_id: int, start_time: datetime, end_time: datetime
    ) -> bool:
        """Check if time period conflicts with staff time off."""
        query = select(TimeOff).where(
            and_(
                TimeOff.owner_type == OwnerType.STAFF.value,
                TimeOff.owner_id == staff_id,
                TimeOff.status == TimeOffStatus.APPROVED.value,
                or_(
                    and_(
                        TimeOff.start_datetime <= start_time,
                        TimeOff.end_datetime > start_time,
                    ),
                    and_(
                        TimeOff.start_datetime < end_time,
                        TimeOff.end_datetime >= end_time,
                    ),
                    and_(
                        TimeOff.start_datetime >= start_time,
                        TimeOff.end_datetime <= end_time,
                    ),
                ),
            )
        )
        result = await self.db.execute(query)
        time_off = result.scalar_one_or_none()

        return time_off is not None

    async def _check_availability_overrides(
        self, staff_id: int, start_time: datetime, end_time: datetime
    ) -> Optional[str]:
        """Check availability overrides and return effect."""
        query = select(AvailabilityOverride).where(
            and_(
                AvailabilityOverride.staff_id == staff_id,
                AvailabilityOverride.is_active,
                or_(
                    and_(
                        AvailabilityOverride.start_datetime <= start_time,
                        AvailabilityOverride.end_datetime > start_time,
                    ),
                    and_(
                        AvailabilityOverride.start_datetime < end_time,
                        AvailabilityOverride.end_datetime >= end_time,
                    ),
                    and_(
                        AvailabilityOverride.start_datetime >= start_time,
                        AvailabilityOverride.end_datetime <= end_time,
                    ),
                ),
            )
        )
        result = await self.db.execute(query)
        overrides = result.scalars().all()

        for override in overrides:
            effect = override.affects_availability_at(start_time)
            if effect:
                return effect

        return None

    async def _has_appointment_conflict(
        self, staff_id: int, start_time: datetime, end_time: datetime
    ) -> bool:
        """Check if time period conflicts with existing appointments."""
        from app.models.appointment import Appointment, AppointmentStatus

        logger.debug(
            f"Checking for appointment conflicts for staff {staff_id} from {start_time} to {end_time}"
        )

        # Query for active appointments that overlap with the requested time period
        query = select(Appointment).where(
            and_(
                Appointment.staff_id == staff_id,
                ~Appointment.is_cancelled,  # Only check non-cancelled appointments
                Appointment.status.in_(
                    [
                        AppointmentStatus.TENTATIVE.value,
                        AppointmentStatus.CONFIRMED.value,
                        AppointmentStatus.IN_PROGRESS.value,
                    ]
                ),
                or_(
                    # New appointment starts during existing appointment
                    and_(
                        Appointment.scheduled_datetime <= start_time,
                        Appointment.estimated_end_datetime > start_time,
                    ),
                    # New appointment ends during existing appointment
                    and_(
                        Appointment.scheduled_datetime < end_time,
                        Appointment.estimated_end_datetime >= end_time,
                    ),
                    # New appointment completely contains existing appointment
                    and_(
                        Appointment.scheduled_datetime >= start_time,
                        Appointment.estimated_end_datetime <= end_time,
                    ),
                ),
            )
        )

        result = await self.db.execute(query)
        conflicting_appointment = result.scalar_one_or_none()

        if conflicting_appointment:
            logger.debug(
                f"Found conflicting appointment: {conflicting_appointment.scheduled_datetime} - {conflicting_appointment.estimated_end_datetime}"
            )
            return True
        else:
            logger.debug("No appointment conflicts found")
            return False

    async def _check_lead_time_policy(
        self, business_id: int, service: Service, requested_time: datetime
    ) -> bool:
        """Check if appointment meets minimum lead time requirements."""
        query = select(Business).where(Business.id == business_id)
        result = await self.db.execute(query)
        business = result.scalar_one_or_none()
        if not business:
            return False

        # Get lead time from service or business policy
        min_lead_time_hours = service.min_lead_time_hours

        if min_lead_time_hours is None and business.policy:
            min_lead_time_hours = business.policy.get("min_lead_time_hours", 0)

        if min_lead_time_hours is None:
            min_lead_time_hours = 0

        if min_lead_time_hours <= 0:
            return True

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        min_booking_time = now + timedelta(hours=min_lead_time_hours)

        return requested_time >= min_booking_time

    async def _check_advance_booking_policy(
        self, business_id: int, service: Service, requested_time: datetime
    ) -> bool:
        """Check if appointment is within maximum advance booking period."""
        query = select(Business).where(Business.id == business_id)
        result = await self.db.execute(query)
        business = result.scalar_one_or_none()
        if not business:
            return False

        # Get advance booking limit from service or business policy
        max_advance_days = service.max_advance_booking_days

        if max_advance_days is None and business.policy:
            max_advance_days = business.policy.get("max_advance_booking_days")

        if max_advance_days is None:
            return True  # No limit

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        max_booking_time = now + timedelta(days=max_advance_days)

        return requested_time <= max_booking_time

    async def _find_alternative_slots(
        self,
        staff: Staff,
        service: Service,
        preferred_time: datetime,
        duration_minutes: int,
    ) -> list[AvailabilitySlot]:
        """Find alternative available slots around the preferred time."""

        # Search for alternatives within 7 days of preferred time
        search_start = preferred_time.replace(hour=0, minute=0, second=0, microsecond=0)
        search_end = search_start + timedelta(days=7)

        # Create availability query
        query = StaffAvailabilityQuery(
            staff_uuid=str(staff.uuid),
            start_datetime=search_start,
            end_datetime=search_end,
            service_uuid=str(service.uuid),
            include_busy_slots=False,
            slot_duration_minutes=duration_minutes,
        )

        slots = await self.get_staff_availability(query)

        # Filter to available slots and limit to reasonable number
        available_slots = [
            slot for slot in slots if slot.status == AvailabilityStatus.AVAILABLE
        ][:10]

        return available_slots

    async def _calculate_addon_duration(self, addon_uuids: list[str]) -> int:
        """Calculate total duration of service addons."""
        if not addon_uuids:
            return 0

        from sqlalchemy import and_

        from app.models.service_addon import ServiceAddon

        result = await self.db.execute(
            select(ServiceAddon.extra_duration_minutes).where(
                and_(ServiceAddon.uuid.in_(addon_uuids), ServiceAddon.is_active)
            )
        )
        durations = result.scalars().all()
        return sum(durations) if durations else 0

    async def _get_staff_by_uuid(self, staff_uuid: str) -> Optional[Staff]:
        """Get staff by UUID."""
        result = await self.db.execute(select(Staff).filter(Staff.uuid == staff_uuid))
        return result.scalar_one_or_none()

    async def _get_service_by_uuid(self, service_uuid: str) -> Optional[Service]:
        """Get service by UUID."""
        result = await self.db.execute(
            select(Service).filter(Service.uuid == service_uuid)
        )
        return result.scalar_one_or_none()

    async def _get_business_by_id(self, business_id: int) -> Optional[Business]:
        """Get business by ID."""
        result = await self.db.execute(
            select(Business).filter(Business.id == business_id)
        )
        return result.scalar_one_or_none()

    async def get_business_hours(self, query: BusinessHoursQuery) -> dict[str, Any]:
        """Get business hours for a specific date."""
        query_business = select(Business).where(Business.uuid == query.business_uuid)
        result = await self.db.execute(query_business)
        business = result.scalar_one_or_none()
        if not business:
            return {}

        weekday = WeekDay(query.date.weekday())

        query_hours = select(WorkingHours).where(
            and_(
                WorkingHours.owner_type == OwnerType.BUSINESS.value,
                WorkingHours.owner_id == business.id,
                WorkingHours.weekday == weekday.name,
                WorkingHours.is_active is True,
            )
        )
        result_hours = await self.db.execute(query_hours)
        working_hours = result_hours.scalar_one_or_none()

        if not working_hours:
            return {"is_open": False, "weekday": weekday.name, "hours": None}

        result = {
            "is_open": True,
            "weekday": weekday.name,
            "hours": {
                "start_time": working_hours.start_time.isoformat(),
                "end_time": working_hours.end_time.isoformat(),
                "duration_minutes": working_hours.duration_minutes,
            },
        }

        if query.include_breaks and working_hours.break_start_time:
            result["hours"]["break"] = {
                "start_time": working_hours.break_start_time.isoformat(),
                "end_time": working_hours.break_end_time.isoformat(),
            }

        # Apply pre-holiday cutoff to the returned hours if applicable
        if HolidayService.is_day_before_holiday(query.date):
            # Display local end time of 15:00 on holiday eve
            result["hours"]["end_time"] = "15:00:00"

        return result

    async def get_staff_schedule(self, query: StaffScheduleQuery) -> dict[str, Any]:
        """Get comprehensive staff schedule including all relevant information."""
        staff = await self._get_staff_by_uuid(query.staff_uuid)
        if not staff:
            return {}

        result = {
            "staff_uuid": query.staff_uuid,
            "start_date": query.start_date.date().isoformat(),
            "end_date": query.end_date.date().isoformat(),
            "working_hours": [],
            "time_off": [],
            "availability_overrides": [],
            "appointments": [],
        }

        # Get working hours
        current_date = query.start_date.date()
        end_date = query.end_date.date()

        while current_date <= end_date:
            weekday = WeekDay(current_date.weekday())

            query_wh = select(WorkingHours).where(
                and_(
                    WorkingHours.owner_type == OwnerType.STAFF.value,
                    WorkingHours.owner_id == staff.id,
                    WorkingHours.weekday == weekday.name,
                    WorkingHours.is_active,
                )
            )
            result_wh = await self.db.execute(query_wh)
            working_hours = result_wh.scalar_one_or_none()

            if working_hours:
                result["working_hours"].append(
                    {
                        "date": current_date.isoformat(),
                        "weekday": weekday.name,
                        "start_time": working_hours.start_time.isoformat(),
                        "end_time": working_hours.end_time.isoformat(),
                        "break_start_time": (
                            working_hours.break_start_time.isoformat()
                            if working_hours.break_start_time
                            else None
                        ),
                        "break_end_time": (
                            working_hours.break_end_time.isoformat()
                            if working_hours.break_end_time
                            else None
                        ),
                    }
                )

            current_date += timedelta(days=1)

        # Get time off if requested
        if query.include_time_off:
            query_timeoff = select(TimeOff).where(
                and_(
                    TimeOff.owner_type == OwnerType.STAFF.value,
                    TimeOff.owner_id == staff.id,
                    TimeOff.status == TimeOffStatus.APPROVED.value,
                    or_(
                        and_(
                            TimeOff.start_datetime >= query.start_date,
                            TimeOff.start_datetime <= query.end_date,
                        ),
                        and_(
                            TimeOff.end_datetime >= query.start_date,
                            TimeOff.end_datetime <= query.end_date,
                        ),
                        and_(
                            TimeOff.start_datetime <= query.start_date,
                            TimeOff.end_datetime >= query.end_date,
                        ),
                    ),
                )
            )
            result_timeoff = await self.db.execute(query_timeoff)
            time_offs = result_timeoff.scalars().all()

            for time_off in time_offs:
                result["time_off"].append(
                    {
                        "uuid": str(time_off.uuid),
                        "type": (
                            time_off.type.value
                            if hasattr(time_off.type, "value")
                            else str(time_off.type)
                        ),
                        "start_datetime": time_off.start_datetime.isoformat(),
                        "end_datetime": time_off.end_datetime.isoformat(),
                        "reason": time_off.reason,
                        "is_all_day": time_off.is_all_day,
                    }
                )

        # Get availability overrides if requested
        if query.include_availability_overrides:
            query_overrides = select(AvailabilityOverride).where(
                and_(
                    AvailabilityOverride.staff_id == staff.id,
                    AvailabilityOverride.is_active,
                    or_(
                        and_(
                            AvailabilityOverride.start_datetime >= query.start_date,
                            AvailabilityOverride.start_datetime <= query.end_date,
                        ),
                        and_(
                            AvailabilityOverride.end_datetime >= query.start_date,
                            AvailabilityOverride.end_datetime <= query.end_date,
                        ),
                        and_(
                            AvailabilityOverride.start_datetime <= query.start_date,
                            AvailabilityOverride.end_datetime >= query.end_date,
                        ),
                    ),
                )
            )
            result_overrides = await self.db.execute(query_overrides)
            overrides = result_overrides.scalars().all()

            for override in overrides:
                result["availability_overrides"].append(
                    {
                        "uuid": str(override.uuid),
                        "type": (
                            override.override_type.value
                            if hasattr(override.override_type, "value")
                            else str(override.override_type)
                        ),
                        "start_datetime": override.start_datetime.isoformat(),
                        "end_datetime": override.end_datetime.isoformat(),
                        "title": override.title,
                        "reason": override.reason,
                        "allow_new_bookings": override.allow_new_bookings,
                    }
                )

        # Note: Appointments would be added here when appointment model is finalized

        return result
