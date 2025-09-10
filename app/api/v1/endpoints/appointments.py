from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_staff
from app.api.deps.database import get_db
from app.models.staff import Staff
from app.schemas.appointment import (
    Appointment,
    AppointmentCreate,
    AppointmentFilters,
    AppointmentList,
    AppointmentReschedule,
    AppointmentSearch,
    AppointmentSlotLock,
    AppointmentStats,
    AppointmentStatus,
    AppointmentStatusTransition,
    AppointmentUpdate,
    AppointmentWithRelations,
    BookingSourceSchema,
    BulkAppointmentResponse,
    BulkAppointmentStatusUpdate,
    CancellationPolicyCheck,
    CancellationPolicyResponse,
    ConflictCheckRequest,
    ConflictCheckResponse,
)
from app.schemas.scheduling import StaffAvailabilityQuery
from app.services.appointment import AppointmentService

router = APIRouter()


@router.post("/", response_model=Appointment, status_code=status.HTTP_201_CREATED)
async def create_appointment(
    appointment_data: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
    session_id: Optional[str] = Query(None, description="Session ID for slot locking"),
):
    """Create new appointment with validation and conflict checking."""
    appointment_data.business_id = current_staff.business_id

    service = AppointmentService(db)
    try:
        appointment = await service.create_appointment(appointment_data, session_id)
        await db.commit()
        return appointment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create appointment",
        )


@router.get("/", response_model=AppointmentList)
async def get_appointments(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
    # Search parameters
    query: Optional[str] = Query(
        None, description="Search in customer, staff, or service names"
    ),
    # Filter parameters
    customer_id: Optional[int] = Query(None),
    staff_id: Optional[int] = Query(None),
    service_id: Optional[int] = Query(None),
    status: Optional[AppointmentStatus] = Query(None),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    booking_source: Optional[BookingSourceSchema] = Query(None),
    is_cancelled: Optional[bool] = Query(None),
    is_no_show: Optional[bool] = Query(None),
    deposit_paid: Optional[bool] = Query(None),
    # Pagination parameters
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query(
        "scheduled_datetime",
        regex=r"^(scheduled_datetime|created_at|status|total_price)$",
    ),
    sort_order: str = Query("asc", regex=r"^(asc|desc)$"),
):
    """Get appointments with filtering, search, and pagination."""

    filters = AppointmentFilters(
        business_id=current_staff.business_id,
        customer_id=customer_id,
        staff_id=staff_id,
        service_id=service_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        booking_source=booking_source,
        is_cancelled=is_cancelled,
        is_no_show=is_no_show,
        deposit_paid=deposit_paid,
    )

    search = AppointmentSearch(
        query=query,
        filters=filters,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )

    service = AppointmentService(db)
    appointments, total_count = await service.get_appointments(
        search, current_staff.business_id
    )

    total_pages = (total_count + page_size - 1) // page_size

    return AppointmentList(
        appointments=appointments,
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/calendar")
async def get_calendar_data(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
    date: Optional[str] = Query(
        None, description="Optional date filter for calendar data"
    ),
):
    """Get calendar data including staff, services, customers, and appointments."""
    from app.services.staff_management import StaffManagementService
    from app.services.service import ServiceManagementService
    from app.services.customer import customer_service
    from app.schemas.appointment import AppointmentSearch, AppointmentFilters

    try:
        # Get all data needed for calendar
        staff_service = StaffManagementService(db)
        appointment_service = AppointmentService(db)

        # Get staff members with their services
        staff_members_raw = await staff_service.list_staff(
            business_id=current_staff.business_id, include_inactive=False
        )

        # Convert staff to dict format for proper serialization
        staff_members = []
        for staff in staff_members_raw:
            staff_dict = {
                "id": staff.id,
                "uuid": str(staff.uuid),
                "name": staff.name,
                "email": staff.email,
                "phone": staff.phone,
                "avatar_url": staff.avatar_url,
                "bio": staff.bio,
                "role": staff.role,
                "is_bookable": staff.is_bookable,
                "is_active": staff.is_active,
                "display_order": staff.display_order,
            }
            staff_members.append(staff_dict)

        # Get staff services for pricing/duration overrides
        from app.models.staff_service import StaffService
        from sqlalchemy.orm import selectinload
        from sqlalchemy import select

        staff_services_query = (
            select(StaffService)
            .options(
                selectinload(StaffService.staff), selectinload(StaffService.service)
            )
            .where(StaffService.staff_id.in_([s["id"] for s in staff_members]))
        )

        staff_services_result = await db.execute(staff_services_query)
        staff_services = staff_services_result.scalars().all()

        # Get services
        services_raw = await ServiceManagementService.get_services(
            db, business_id=current_staff.business_id, is_active=True
        )

        # Convert services to dict format with proper decimal handling
        services = []
        for service in services_raw:
            service_dict = {
                "id": service.id,
                "uuid": str(service.uuid),
                "name": service.name,
                "description": service.description,
                "duration_min": service.duration_minutes,
                "price": float(service.price) if service.price else 0.0,
                "buffer_before_minutes": service.buffer_before_minutes,
                "buffer_after_minutes": service.buffer_after_minutes,
                "is_active": service.is_active,
                "requires_deposit": service.requires_deposit,
                "deposit_amount": (
                    float(service.deposit_amount) if service.deposit_amount else None
                ),
                "max_advance_booking_days": service.max_advance_booking_days,
                "min_lead_time_hours": service.min_lead_time_hours,
                "sort_order": service.sort_order,
                "image_url": service.image_url,
                "color": service.color,
            }
            services.append(service_dict)

        # Get customers
        customers_raw = await customer_service.get_customers(
            db, business_id=current_staff.business_id, limit=1000, include_inactive=True
        )

        # Map customers to frontend format
        from app.schemas.customer import CustomerResponse

        customers = [CustomerResponse.from_orm(customer) for customer in customers_raw]

        # Get appointments - if date is provided, filter by date range
        if date:
            from datetime import datetime, timedelta

            try:
                target_date = datetime.fromisoformat(date.replace("Z", "+00:00"))
                start_date = target_date.replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                end_date = start_date + timedelta(days=1)

                # Create search filters for date range
                filters = AppointmentFilters(
                    business_id=current_staff.business_id,
                    start_date=start_date,
                    end_date=end_date,
                )
            except ValueError:
                # If date parsing fails, get all appointments
                filters = AppointmentFilters(business_id=current_staff.business_id)
        else:
            filters = AppointmentFilters(business_id=current_staff.business_id)

        # Create search object
        search = AppointmentSearch(
            query=None,
            filters=filters,
            page=1,
            page_size=100,  # Maximum allowed page size
            sort_by="scheduled_datetime",
            sort_order="asc",
        )

        appointments_raw, _ = await appointment_service.get_appointments(search)

        # Convert appointments to dict format with proper decimal handling
        appointments = []
        for appointment in appointments_raw:
            appointment_dict = {
                "id": appointment.id,
                "uuid": str(appointment.uuid),
                "business_id": appointment.business_id,
                "customer_id": appointment.customer_id,
                "staff_id": appointment.staff_id,
                "service_id": appointment.service_id,
                "scheduled_datetime": (
                    appointment.scheduled_datetime.isoformat()
                    if appointment.scheduled_datetime
                    else None
                ),
                "estimated_end_datetime": (
                    appointment.estimated_end_datetime.isoformat()
                    if appointment.estimated_end_datetime
                    else None
                ),
                "actual_start_datetime": (
                    appointment.actual_start_datetime.isoformat()
                    if appointment.actual_start_datetime
                    else None
                ),
                "actual_end_datetime": (
                    appointment.actual_end_datetime.isoformat()
                    if appointment.actual_end_datetime
                    else None
                ),
                "duration_minutes": appointment.duration_minutes,
                "status": appointment.status,
                "previous_status": appointment.previous_status,
                "status_changed_at": (
                    appointment.status_changed_at.isoformat()
                    if appointment.status_changed_at
                    else None
                ),
                "booked_by_staff_id": appointment.booked_by_staff_id,
                "booking_source": appointment.booking_source,
                "total_price": (
                    float(appointment.total_price) if appointment.total_price else 0.0
                ),
                "deposit_required": appointment.deposit_required,
                "deposit_amount": (
                    float(appointment.deposit_amount)
                    if appointment.deposit_amount
                    else None
                ),
                "deposit_paid": appointment.deposit_paid,
                "deposit_paid_at": (
                    appointment.deposit_paid_at.isoformat()
                    if appointment.deposit_paid_at
                    else None
                ),
                "is_cancelled": appointment.is_cancelled,
                "cancelled_at": (
                    appointment.cancelled_at.isoformat()
                    if appointment.cancelled_at
                    else None
                ),
                "cancelled_by_staff_id": appointment.cancelled_by_staff_id,
                "cancellation_reason": appointment.cancellation_reason,
                "cancellation_notes": appointment.cancellation_notes,
                "cancellation_fee": (
                    float(appointment.cancellation_fee)
                    if appointment.cancellation_fee
                    else None
                ),
                "original_appointment_id": appointment.original_appointment_id,
                "rescheduled_from_datetime": (
                    appointment.rescheduled_from_datetime.isoformat()
                    if appointment.rescheduled_from_datetime
                    else None
                ),
                "reschedule_count": appointment.reschedule_count,
                "customer_notes": appointment.customer_notes,
                "internal_notes": appointment.internal_notes,
                "reminder_sent_at": (
                    appointment.reminder_sent_at.isoformat()
                    if appointment.reminder_sent_at
                    else None
                ),
                "confirmation_sent_at": (
                    appointment.confirmation_sent_at.isoformat()
                    if appointment.confirmation_sent_at
                    else None
                ),
                "is_no_show": appointment.is_no_show,
                "no_show_fee": (
                    float(appointment.no_show_fee) if appointment.no_show_fee else None
                ),
                "slot_locked": appointment.slot_locked,
                "slot_locked_at": (
                    appointment.slot_locked_at.isoformat()
                    if appointment.slot_locked_at
                    else None
                ),
                "slot_lock_expires_at": (
                    appointment.slot_lock_expires_at.isoformat()
                    if appointment.slot_lock_expires_at
                    else None
                ),
                "locked_by_session_id": appointment.locked_by_session_id,
                "created_at": (
                    appointment.created_at.isoformat()
                    if appointment.created_at
                    else None
                ),
                "updated_at": (
                    appointment.updated_at.isoformat()
                    if appointment.updated_at
                    else None
                ),
            }
            appointments.append(appointment_dict)

        # Debug logging
        print(f"Calendar data - Staff count: {len(staff_members)}")
        print(f"Calendar data - Services count: {len(services)}")
        print(f"Calendar data - Customers count: {len(customers)}")
        print(f"Calendar data - Appointments count: {len(appointments)}")

        # Convert staff services to dict format for frontend
        staff_services_data = []
        for staff_service in staff_services:
            # Ensure all decimal values are converted to float for JSON serialization
            effective_price = staff_service.effective_price
            if hasattr(effective_price, "__float__"):
                effective_price = float(effective_price)

            staff_services_data.append(
                {
                    "staff_id": staff_service.staff_id,
                    "service_id": staff_service.service_id,
                    "effective_duration_minutes": staff_service.effective_duration_minutes,
                    "effective_price": effective_price,
                    "is_available": staff_service.is_available,
                    "expertise_level": staff_service.expertise_level,
                }
            )

        return {
            "staff": staff_members,
            "services": services,
            "customers": customers,
            "appointments": appointments,
            "staff_services": staff_services_data,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get calendar data: {str(e)}",
        )


@router.post("/check-availability")
async def check_availability(
    request: StaffAvailabilityQuery,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Check staff availability for a specific time slot."""
    try:
        from app.services.scheduling import SchedulingEngineService

        scheduling_service = SchedulingEngineService(db)
        availability_slots = await scheduling_service.get_staff_availability(request)

        return {
            "available_slots": availability_slots,
            "is_available": len(availability_slots) > 0
            and any(slot.status == "available" for slot in availability_slots),
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check availability: {str(e)}",
        )


@router.get("/{appointment_uuid}", response_model=AppointmentWithRelations)
async def get_appointment(
    appointment_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Get specific appointment with all relationships."""

    service = AppointmentService(db)
    appointment = await service.get_appointment_by_uuid(str(appointment_uuid))

    if not appointment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    if appointment.business_id != current_staff.business_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
        )

    return appointment


@router.put("/{appointment_uuid}", response_model=Appointment)
async def update_appointment(
    appointment_uuid: UUID,
    update_data: AppointmentUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Update appointment details."""

    service = AppointmentService(db)

    # Verify appointment exists and belongs to business
    existing_appointment = await service.get_appointment_by_uuid(str(appointment_uuid))
    if (
        not existing_appointment
        or existing_appointment.business_id != current_staff.business_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    try:
        appointment = await service.update_appointment(
            str(appointment_uuid), update_data
        )
        await db.commit()
        return appointment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update appointment",
        )


@router.post("/{appointment_uuid}/status", response_model=Appointment)
async def transition_appointment_status(
    appointment_uuid: UUID,
    transition: AppointmentStatusTransition,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Transition appointment status (confirm, complete, cancel, etc.)."""

    service = AppointmentService(db)

    # Verify appointment exists and belongs to staff's business
    existing_appointment = await service.get_appointment_by_uuid(str(appointment_uuid))
    if (
        not existing_appointment
        or existing_appointment.business_id != current_staff.business_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    try:
        appointment = await service.transition_appointment_status(
            str(appointment_uuid), transition, staff_id=current_staff.id
        )
        await db.commit()
        return appointment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to transition status",
        )


@router.post("/{appointment_uuid}/reschedule", response_model=Appointment)
async def reschedule_appointment(
    appointment_uuid: UUID,
    reschedule_data: AppointmentReschedule,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Reschedule appointment to new datetime."""

    service = AppointmentService(db)

    # Verify appointment exists and belongs to business
    existing_appointment = await service.get_appointment_by_uuid(str(appointment_uuid))
    if (
        not existing_appointment
        or existing_appointment.business_id != current_staff.business_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    try:
        appointment = await service.reschedule_appointment(
            str(appointment_uuid), reschedule_data
        )
        await db.commit()
        return appointment
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reschedule appointment",
        )


@router.post("/{appointment_uuid}/lock", status_code=status.HTTP_200_OK)
async def lock_appointment_slot(
    appointment_uuid: UUID,
    lock_data: AppointmentSlotLock,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Lock appointment slot to prevent conflicts during booking process."""

    service = AppointmentService(db)

    # Verify appointment exists and belongs to business
    existing_appointment = await service.get_appointment_by_uuid(str(appointment_uuid))
    if (
        not existing_appointment
        or existing_appointment.business_id != current_staff.business_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    success = await service.lock_appointment_slot(str(appointment_uuid), lock_data)
    if success:
        await db.commit()
        return {"message": "Slot locked successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slot already locked by another session",
        )


@router.delete("/{appointment_uuid}/lock", status_code=status.HTTP_200_OK)
async def unlock_appointment_slot(
    appointment_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
    session_id: Optional[str] = Query(None),
):
    """Unlock appointment slot."""

    service = AppointmentService(db)

    # Verify appointment exists and belongs to business
    existing_appointment = await service.get_appointment_by_uuid(str(appointment_uuid))
    if (
        not existing_appointment
        or existing_appointment.business_id != current_staff.business_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    success = await service.unlock_appointment_slot(str(appointment_uuid), session_id)
    if success:
        await db.commit()
        return {"message": "Slot unlocked successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Cannot unlock slot"
        )


@router.delete("/{appointment_uuid}", status_code=status.HTTP_200_OK)
async def delete_appointment(
    appointment_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Delete appointment (soft delete by cancelling)."""

    service = AppointmentService(db)

    # Verify appointment exists and belongs to business
    existing_appointment = await service.get_appointment_by_uuid(str(appointment_uuid))
    if (
        not existing_appointment
        or existing_appointment.business_id != current_staff.business_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    success = await service.delete_appointment(str(appointment_uuid))
    if success:
        await db.commit()
        return {"message": "Appointment deleted successfully"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete appointment",
        )


@router.post("/check-cancellation-policy", response_model=CancellationPolicyResponse)
async def check_cancellation_policy(
    check: CancellationPolicyCheck,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Check if appointment can be cancelled based on business policy."""

    service = AppointmentService(db)

    # Verify appointment belongs to business
    existing_appointment = await service.get_appointment_by_uuid(
        str(check.appointment_uuid)
    )
    if (
        not existing_appointment
        or existing_appointment.business_id != current_staff.business_id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Appointment not found"
        )

    return await service.check_cancellation_policy(check)


@router.post("/check-conflicts", response_model=ConflictCheckResponse)
async def check_appointment_conflicts(
    check: ConflictCheckRequest,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Check for appointment conflicts with existing bookings."""

    service = AppointmentService(db)
    return await service.check_appointment_conflicts(check)


@router.post("/bulk-status-update", response_model=BulkAppointmentResponse)
async def bulk_update_appointment_status(
    bulk_update: BulkAppointmentStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
):
    """Bulk update appointment statuses."""

    service = AppointmentService(db)
    result = await service.bulk_update_status(bulk_update)
    await db.commit()
    return result


@router.get("/analytics/stats", response_model=AppointmentStats)
async def get_appointment_stats(
    db: AsyncSession = Depends(get_db),
    current_staff: Staff = Depends(get_current_staff),
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
):
    """Get appointment statistics and analytics."""

    service = AppointmentService(db)
    return await service.get_appointment_stats(
        current_staff.business_id, start_date, end_date
    )
