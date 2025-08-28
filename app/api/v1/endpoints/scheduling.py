from datetime import datetime, timedelta
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.database import get_db
from app.services.scheduling import SchedulingEngineService
from app.schemas.scheduling import (
    StaffAvailabilityQuery,
    AvailabilitySlot,
    AppointmentValidationRequest,
    AppointmentValidationResponse,
    BusinessHoursQuery,
    StaffScheduleQuery,
)

router = APIRouter()


@router.get("/staff/availability")
async def get_staff_availability(
    staff_uuid: str = Query(..., description="Staff member UUID"),
    start_datetime: datetime = Query(
        ..., description="Start datetime for availability check"
    ),
    end_datetime: datetime = Query(
        ..., description="End datetime for availability check"
    ),
    service_uuid: str = Query(
        None, description="Optional service UUID to check compatibility"
    ),
    slot_duration_minutes: int = Query(
        15, description="Duration of each availability slot in minutes"
    ),
    include_busy_slots: bool = Query(
        False, description="Include unavailable/busy slots in response"
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, List[AvailabilitySlot]]:
    """
    Get available time slots for a staff member within the specified time range.

    This endpoint calculates staff availability considering:
    - Business working hours
    - Staff working hours
    - Existing appointments
    - Time off periods
    - Availability overrides
    - Service duration and buffer requirements
    - Lead time and advance booking policies
    """
    try:
        scheduling_service = SchedulingEngineService(db)

        query = StaffAvailabilityQuery(
            staff_uuid=staff_uuid,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            service_uuid=service_uuid,
            slot_duration_minutes=slot_duration_minutes,
            include_busy_slots=include_busy_slots,
        )

        slots = await scheduling_service.get_staff_availability(query)

        return {"slots": slots}

    except Exception as e:

        raise HTTPException(
            status_code=500, detail=f"Failed to get staff availability: {str(e)}"
        )


@router.post("/appointments/validate")
async def validate_appointment(
    request: AppointmentValidationRequest, db: AsyncSession = Depends(get_db)
) -> AppointmentValidationResponse:
    """
    Validate if an appointment can be scheduled at the requested time.

    This endpoint performs comprehensive validation including:
    - Staff availability at requested time
    - Service duration and buffer requirements
    - Business and staff working hours compliance
    - Time off conflicts
    - Existing appointment conflicts
    - Lead time policy compliance
    - Advance booking policy compliance
    - Service addon compatibility

    If validation fails, provides alternative time slots when possible.
    """
    try:
        scheduling_service = SchedulingEngineService(db)
        response = await scheduling_service.validate_appointment(request)
        return response

    except Exception as e:
        print(f"EXCEPTION IS {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to validate appointment: {str(e)}"
        )


@router.get("/business/hours")
async def get_business_hours(
    business_uuid: str = Query(..., description="Business UUID"),
    date: datetime = Query(..., description="Date to check business hours for"),
    include_breaks: bool = Query(True, description="Include break times in response"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get business operating hours for a specific date.

    Returns information about:
    - Whether business is open on the specified date
    - Operating hours (start/end times)
    - Break times (if applicable and requested)
    - Weekday information
    """
    try:
        scheduling_service = SchedulingEngineService(db)

        query = BusinessHoursQuery(
            business_uuid=business_uuid, date=date, include_breaks=include_breaks
        )

        hours = await scheduling_service.get_business_hours(query)
        return hours

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get business hours: {str(e)}"
        )


@router.get("/staff/schedule")
async def get_staff_schedule(
    staff_uuid: str = Query(..., description="Staff member UUID"),
    start_date: datetime = Query(..., description="Start date for schedule retrieval"),
    end_date: datetime = Query(..., description="End date for schedule retrieval"),
    include_appointments: bool = Query(
        True, description="Include existing appointments"
    ),
    include_time_off: bool = Query(
        True, description="Include approved time off periods"
    ),
    include_availability_overrides: bool = Query(
        True, description="Include availability overrides"
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Get comprehensive schedule information for a staff member.

    Returns detailed schedule data including:
    - Working hours for each day in the date range
    - Approved time off periods
    - Availability overrides (temporary schedule changes)
    - Existing appointments (if requested)

    This endpoint is useful for schedule management and calendar views.
    """
    try:
        scheduling_service = SchedulingEngineService(db)

        query = StaffScheduleQuery(
            staff_uuid=staff_uuid,
            start_date=start_date,
            end_date=end_date,
            include_appointments=include_appointments,
            include_time_off=include_time_off,
            include_availability_overrides=include_availability_overrides,
        )

        schedule = await scheduling_service.get_staff_schedule(query)
        return schedule

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get staff schedule: {str(e)}"
        )


@router.get("/staff/{staff_uuid}/conflicts")
async def check_scheduling_conflicts(
    staff_uuid: str,
    start_datetime: datetime = Query(
        ..., description="Start datetime to check for conflicts"
    ),
    end_datetime: datetime = Query(
        ..., description="End datetime to check for conflicts"
    ),
    service_uuid: str = Query(
        None, description="Optional service UUID for service-specific validation"
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Check for scheduling conflicts in a specific time range for a staff member.

    Returns detailed information about any conflicts found:
    - Time off periods
    - Existing appointments
    - Working hours violations
    - Availability override conflicts
    - Policy violations (lead time, advance booking)
    """
    try:
        scheduling_service = SchedulingEngineService(db)

        # Use the availability check to identify conflicts
        query = StaffAvailabilityQuery(
            staff_uuid=staff_uuid,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            service_uuid=service_uuid,
            slot_duration_minutes=(end_datetime - start_datetime).total_seconds() / 60,
            include_busy_slots=True,
        )

        slots = await scheduling_service.get_staff_availability(query)

        # Aggregate conflicts from all slots
        all_conflicts = []
        for slot in slots:
            all_conflicts.extend(slot.conflicts)

        # Remove duplicates while preserving order
        unique_conflicts = []
        seen = set()
        for conflict in all_conflicts:
            if conflict not in seen:
                unique_conflicts.append(conflict)
                seen.add(conflict)

        return {
            "staff_uuid": staff_uuid,
            "start_datetime": start_datetime,
            "end_datetime": end_datetime,
            "has_conflicts": len(unique_conflicts) > 0,
            "conflicts": unique_conflicts,
            "total_conflict_count": len(unique_conflicts),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to check scheduling conflicts: {str(e)}"
        )


@router.get("/availability/bulk")
async def get_bulk_availability(
    staff_uuids: List[str] = Query(..., description="List of staff UUIDs to check"),
    start_datetime: datetime = Query(
        ..., description="Start datetime for availability check"
    ),
    end_datetime: datetime = Query(
        ..., description="End datetime for availability check"
    ),
    service_uuid: str = Query(None, description="Optional service UUID"),
    slot_duration_minutes: int = Query(30, description="Slot duration in minutes"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Dict[str, List[AvailabilitySlot]]]:
    """
    Get availability for multiple staff members at once.

    This bulk endpoint is useful for:
    - Comparing availability across multiple staff
    - Finding the next available staff member
    - Displaying team availability in calendar views
    """
    try:
        scheduling_service = SchedulingEngineService(db)
        results = {}

        for staff_uuid in staff_uuids:
            try:
                query = StaffAvailabilityQuery(
                    staff_uuid=staff_uuid,
                    start_datetime=start_datetime,
                    end_datetime=end_datetime,
                    service_uuid=service_uuid,
                    slot_duration_minutes=slot_duration_minutes,
                    include_busy_slots=False,
                )

                slots = await scheduling_service.get_staff_availability(query)
                results[staff_uuid] = {"slots": slots}

            except Exception as staff_error:
                results[staff_uuid] = {"error": str(staff_error), "slots": []}

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get bulk availability: {str(e)}"
        )


@router.get("/next-available")
async def find_next_available_slot(
    staff_uuid: str = Query(..., description="Staff member UUID"),
    service_uuid: str = Query(..., description="Service UUID"),
    preferred_datetime: datetime = Query(
        None, description="Preferred datetime (defaults to now + 1 hour)"
    ),
    max_days_ahead: int = Query(7, description="Maximum days to search ahead"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Find the next available appointment slot for a staff member and service.

    This endpoint is useful for:
    - "Book next available" functionality
    - Quick scheduling suggestions
    - Automated appointment rescheduling
    """
    try:
        scheduling_service = SchedulingEngineService(db)

        if preferred_datetime is None:
            preferred_datetime = datetime.utcnow() + timedelta(hours=1)

        # Get service to determine duration
        service = await scheduling_service._get_service_by_uuid(service_uuid)
        if not service:
            raise HTTPException(status_code=404, detail="Service not found")

        search_end = preferred_datetime + timedelta(days=max_days_ahead)

        query = StaffAvailabilityQuery(
            staff_uuid=staff_uuid,
            start_datetime=preferred_datetime,
            end_datetime=search_end,
            service_uuid=service_uuid,
            slot_duration_minutes=service.total_duration_minutes,
            include_busy_slots=False,
        )

        slots = await scheduling_service.get_staff_availability(query)

        # Find first available slot
        next_available = None
        for slot in slots:
            if slot.status.value == "available":
                next_available = slot
                break

        return {
            "staff_uuid": staff_uuid,
            "service_uuid": service_uuid,
            "preferred_datetime": preferred_datetime,
            "next_available_slot": next_available,
            "search_range_days": max_days_ahead,
            "found": next_available is not None,
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to find next available slot: {str(e)}"
        )


@router.post("/availability/reserve")
async def reserve_time_slot(
    staff_uuid: str,
    start_datetime: datetime,
    end_datetime: datetime,
    reservation_minutes: int = Query(
        15, description="How long to reserve the slot (in minutes)"
    ),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """
    Temporarily reserve a time slot to prevent double-booking during checkout.

    This creates a short-term reservation that expires automatically.
    Useful for preventing race conditions during the booking process.

    Note: This is a placeholder implementation. In a production system,
    this would typically use Redis or similar for temporary reservations.
    """
    try:
        # This is a placeholder implementation
        # In production, you would:
        # 1. Validate the slot is available
        # 2. Create a temporary reservation in Redis/cache
        # 3. Set expiration time
        # 4. Return reservation ID

        scheduling_service = SchedulingEngineService(db)

        # Validate the slot is available
        staff = await scheduling_service._get_staff_by_uuid(staff_uuid)
        if not staff:
            raise HTTPException(status_code=404, detail="Staff not found")

        status, conflicts = await scheduling_service._check_slot_availability(
            staff, start_datetime, end_datetime
        )

        if status.value != "available":
            return {
                "reserved": False,
                "reason": "Slot not available",
                "conflicts": conflicts,
            }

        # In production, create actual reservation here
        reservation_id = (
            f"temp_reservation_{staff_uuid}_{int(start_datetime.timestamp())}"
        )
        expires_at = datetime.utcnow() + timedelta(minutes=reservation_minutes)

        return {
            "reserved": True,
            "reservation_id": reservation_id,
            "expires_at": expires_at,
            "staff_uuid": staff_uuid,
            "reserved_slot": {
                "start_datetime": start_datetime,
                "end_datetime": end_datetime,
            },
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to reserve time slot: {str(e)}"
        )
