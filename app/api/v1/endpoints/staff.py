from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps.database import get_db
from app.api.deps.auth import get_current_staff
from app.api.deps.business import get_business_from_header
from app.models.staff import Staff, StaffRole
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    Staff as StaffSchema,
    StaffSummary,
    StaffWithServices,
    WorkingHoursCreate,
    WorkingHours,
    TimeOffCreate,
    TimeOff,
    AvailabilityOverrideCreate,
    AvailabilityOverride,
    StaffAvailabilityQuery,
    StaffAvailabilityResponse,
    StaffServiceOverride,
)
from app.services.staff_management import StaffManagementService

router = APIRouter()


# Staff CRUD Operations
@router.get("/", response_model=List[StaffSummary])
async def get_staff(
    include_inactive: bool = Query(False, description="Include inactive staff members"),
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Get all staff members for the business.

    - **include_inactive**: Whether to include inactive staff members
    - Returns list of staff summaries
    """
    # Check permissions - only staff members can view staff list
    if current_staff.role not in [
        StaffRole.OWNER_ADMIN,
        StaffRole.STAFF,
        StaffRole.FRONT_DESK,
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to view staff list",
        )

    service = StaffManagementService(db)
    staff_list = await service.list_staff(
        business_id=business_context.business_id, include_inactive=include_inactive
    )
    return staff_list


@router.post("/", response_model=StaffSchema, status_code=status.HTTP_201_CREATED)
async def create_staff(
    staff_data: StaffCreate,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Create a new staff member.

    - **staff_data**: Staff member information
    - Returns created staff member
    """
    # Check permissions - only owners/admins can create staff
    if current_staff.role not in [StaffRole.OWNER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners/admins can create staff members",
        )

    # Ensure business_id matches current business context
    if staff_data.business_id != business_context.business_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Business ID must match current business context",
        )

    service = StaffManagementService(db)
    try:
        staff = await service.create_staff(
            staff_data, created_by_staff_id=current_staff.id
        )
        return staff
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create staff member: {str(e)}",
        )


@router.get("/{staff_uuid}", response_model=StaffSchema)
async def get_staff_by_uuid(
    staff_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Get a specific staff member by UUID.

    - **staff_uuid**: UUID of the staff member
    - Returns staff member details
    """
    # Check permissions - staff can only view their own profile unless they're admin
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own staff profile",
        )

    service = StaffManagementService(db)
    staff = await service.get_staff_by_uuid(
        staff_uuid, business_id=business_context.business_id
    )

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )

    return staff


@router.put("/{staff_uuid}", response_model=StaffSchema)
async def update_staff(
    staff_uuid: UUID,
    staff_data: StaffUpdate,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Update a staff member.

    - **staff_uuid**: UUID of the staff member
    - **staff_data**: Updated staff information
    - Returns updated staff member
    """
    # Check permissions - staff can only update their own profile unless they're admin
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only update your own staff profile",
        )

    # Additional permission check for role changes
    if (
        staff_data.role
        and current_staff.role not in [StaffRole.OWNER_ADMIN]
        and staff_data.role != current_staff.role
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners/admins can change staff roles",
        )

    service = StaffManagementService(db)
    staff = await service.update_staff_by_uuid(
        staff_uuid, staff_data, business_id=business_context.business_id
    )

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )

    return staff


@router.delete("/{staff_uuid}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_staff(
    staff_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Delete (deactivate) a staff member.

    - **staff_uuid**: UUID of the staff member
    - Returns no content on success
    """
    # Check permissions - only owners/admins can delete staff
    if current_staff.role not in [StaffRole.OWNER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners/admins can delete staff members",
        )

    # Prevent self-deletion
    if current_staff.uuid == staff_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account",
        )

    service = StaffManagementService(db)
    success = await service.delete_staff_by_uuid(
        staff_uuid, business_id=business_context.business_id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )


# Working Hours Management
@router.post("/{staff_uuid}/working-hours", response_model=List[WorkingHours])
async def set_staff_working_hours(
    staff_uuid: UUID,
    working_hours: List[WorkingHoursCreate],
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Set working hours for a staff member (replaces existing).

    - **staff_uuid**: UUID of the staff member
    - **working_hours**: List of working hours
    - Returns list of created working hours
    """
    # Check permissions - staff can only set their own hours unless they're admin
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only set your own working hours",
        )

    service = StaffManagementService(db)
    try:
        hours = await service.set_staff_working_hours_by_uuid(staff_uuid, working_hours)
        return hours
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set working hours: {str(e)}",
        )


@router.get("/{staff_uuid}/working-hours", response_model=List[WorkingHours])
async def get_staff_working_hours(
    staff_uuid: UUID,
    active_only: bool = Query(True, description="Include only active working hours"),
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Get working hours for a staff member.

    - **staff_uuid**: UUID of the staff member
    - **active_only**: Whether to include only active working hours
    - Returns list of working hours
    """
    # Check permissions - staff can view their own hours, admins can view all
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own working hours",
        )

    service = StaffManagementService(db)
    hours = await service.get_staff_working_hours_by_uuid(
        staff_uuid, active_only=active_only
    )
    return hours


# Time-Off Management
@router.post(
    "/{staff_uuid}/time-off",
    response_model=TimeOff,
    status_code=status.HTTP_201_CREATED,
)
async def create_time_off(
    staff_uuid: UUID,
    time_off_data: TimeOffCreate,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Create a time-off request for a staff member.

    - **staff_uuid**: UUID of the staff member
    - **time_off_data**: Time-off request information
    - Returns created time-off request
    """
    # Check permissions - staff can only create their own time-off unless they're admin
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only create your own time-off requests",
        )

    service = StaffManagementService(db)
    try:
        time_off = await service.create_time_off_by_uuid(
            staff_uuid, time_off_data, created_by_staff_id=current_staff.id
        )
        return time_off
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create time-off request: {str(e)}",
        )


@router.get("/{staff_uuid}/time-off", response_model=List[TimeOff])
async def get_staff_time_offs(
    staff_uuid: UUID,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Get time-off requests for a staff member.

    - **staff_uuid**: UUID of the staff member
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter
    - Returns list of time-off requests
    """
    # Check permissions - staff can view their own time-offs, admins can view all
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own time-off requests",
        )

    # Parse date parameters
    from datetime import datetime

    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD",
            )

    if end_date:
        try:
            parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD",
            )

    service = StaffManagementService(db)
    time_offs = await service.get_staff_time_offs_by_uuid(
        staff_uuid, start_date=parsed_start_date, end_date=parsed_end_date
    )
    return time_offs


@router.post("/time-off/{time_off_uuid}/approve", response_model=TimeOff)
async def approve_time_off(
    time_off_uuid: UUID,
    approval_notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Approve a time-off request.

    - **time_off_uuid**: UUID of the time-off request
    - **approval_notes**: Optional approval notes
    - Returns approved time-off request
    """
    # Check permissions - only owners/admins can approve time-off
    if current_staff.role not in [StaffRole.OWNER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners/admins can approve time-off requests",
        )

    service = StaffManagementService(db)
    try:
        time_off = await service.approve_time_off_by_uuid(
            time_off_uuid,
            approved_by_staff_id=current_staff.id,
            approval_notes=approval_notes,
        )
        return time_off
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve time-off request: {str(e)}",
        )


@router.post("/time-off/{time_off_uuid}/deny", response_model=TimeOff)
async def deny_time_off(
    time_off_uuid: UUID,
    denial_notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Deny a time-off request.

    - **time_off_uuid**: UUID of the time-off request
    - **denial_notes**: Optional denial notes
    - Returns denied time-off request
    """
    # Check permissions - only owners/admins can deny time-off
    if current_staff.role not in [StaffRole.OWNER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners/admins can deny time-off requests",
        )

    service = StaffManagementService(db)
    try:
        time_off = await service.deny_time_off_by_uuid(
            time_off_uuid,
            denied_by_staff_id=current_staff.id,
            denial_notes=denial_notes,
        )
        return time_off
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deny time-off request: {str(e)}",
        )


# Availability Override Management
@router.post(
    "/{staff_uuid}/availability-overrides",
    response_model=AvailabilityOverride,
    status_code=status.HTTP_201_CREATED,
)
async def create_availability_override(
    staff_uuid: UUID,
    override_data: AvailabilityOverrideCreate,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Create an availability override for a staff member.

    - **staff_uuid**: UUID of the staff member
    - **override_data**: Availability override information
    - Returns created availability override
    """
    # Check permissions - staff can only create their own overrides unless they're admin
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only create your own availability overrides",
        )

    # Ensure staff_id in override data matches path parameter
    if override_data.staff_id != staff_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Staff ID in override data must match path parameter",
        )

    service = StaffManagementService(db)
    try:
        override = await service.create_availability_override_by_uuid(
            override_data, created_by_staff_id=current_staff.id
        )
        return override
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create availability override: {str(e)}",
        )


@router.get(
    "/{staff_uuid}/availability-overrides", response_model=List[AvailabilityOverride]
)
async def get_staff_availability_overrides(
    staff_uuid: UUID,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Get availability overrides for a staff member.

    - **staff_uuid**: UUID of the staff member
    - **start_date**: Optional start date filter
    - **end_date**: Optional end date filter
    - Returns list of availability overrides
    """
    # Check permissions - staff can view their own overrides, admins can view all
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own availability overrides",
        )

    # Parse date parameters
    from datetime import datetime

    parsed_start_date = None
    parsed_end_date = None

    if start_date:
        try:
            parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid start_date format. Use YYYY-MM-DD",
            )

    if end_date:
        try:
            parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid end_date format. Use YYYY-MM-DD",
            )

    service = StaffManagementService(db)
    overrides = await service.get_staff_availability_overrides_by_uuid(
        staff_uuid, start_date=parsed_start_date, end_date=parsed_end_date
    )
    return overrides


# Availability Calculation
@router.post("/{staff_uuid}/availability", response_model=StaffAvailabilityResponse)
async def calculate_staff_availability(
    staff_uuid: UUID,
    availability_query: StaffAvailabilityQuery,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Calculate staff availability for a given time period.

    - **staff_uuid**: UUID of the staff member
    - **availability_query**: Query parameters for availability calculation
    - Returns staff availability response
    """
    # Check permissions - staff can check their own availability, admins can check all
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only check your own availability",
        )

    service = StaffManagementService(db)
    try:
        availability = await service.calculate_staff_availability_by_uuid(
            availability_query, staff_uuid
        )
        return availability
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate staff availability: {str(e)}",
        )


# Service Mapping Management
@router.post("/{staff_uuid}/services", response_model=dict)
async def assign_service_to_staff(
    staff_uuid: UUID,
    service_override: StaffServiceOverride,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Assign a service to a staff member with optional overrides.

    - **staff_uuid**: UUID of the staff member
    - **service_override**: Service assignment with overrides
    - Returns created/updated service assignment
    """
    # Check permissions - only owners/admins can assign services
    if current_staff.role not in [StaffRole.OWNER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners/admins can assign services to staff",
        )

    service = StaffManagementService(db)
    try:
        # Convert schema to kwargs for the service method
        overrides = service_override.dict(exclude={"service_id"})
        staff_service = await service.assign_service_to_staff_by_uuid(
            staff_uuid, service_override.service_id, **overrides
        )
        return {
            "message": "Service assigned successfully",
            "staff_service_id": staff_service.id,
            "staff_id": staff_service.staff_id,
            "service_id": staff_service.service_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign service to staff: {str(e)}",
        )


@router.delete(
    "/{staff_uuid}/services/{service_uuid}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_service_from_staff(
    staff_uuid: UUID,
    service_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Remove a service assignment from a staff member.

    - **staff_uuid**: UUID of the staff member
    - **service_uuid**: UUID of the service to remove
    - Returns no content on success
    """
    # Check permissions - only owners/admins can remove service assignments
    if current_staff.role not in [StaffRole.OWNER_ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only business owners/admins can remove service assignments",
        )

    service = StaffManagementService(db)
    success = await service.remove_service_from_staff_by_uuid(staff_uuid, service_uuid)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Service assignment not found"
        )


@router.get("/{staff_uuid}/services", response_model=List[dict])
async def get_staff_services(
    staff_uuid: UUID,
    available_only: bool = Query(True, description="Include only available services"),
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Get all services assigned to a staff member.

    - **staff_uuid**: UUID of the staff member
    - **available_only**: Whether to include only available services
    - Returns list of service assignments
    """
    # Check permissions - staff can view their own services, admins can view all
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own service assignments",
        )

    service = StaffManagementService(db)
    staff_services = await service.get_staff_services_by_uuid(
        staff_uuid, available_only=available_only
    )

    # Convert to response format
    result = []
    for staff_service in staff_services:
        result.append(
            {
                "id": staff_service.id,
                "service_id": staff_service.service_id,
                "staff_id": staff_service.staff_id,
                "override_duration_minutes": staff_service.override_duration_minutes,
                "override_price": staff_service.override_price,
                "override_buffer_before_minutes": staff_service.override_buffer_before_minutes,
                "override_buffer_after_minutes": staff_service.override_buffer_after_minutes,
                "is_available": staff_service.is_available,
                "expertise_level": staff_service.expertise_level,
                "notes": staff_service.notes,
                "requires_approval": staff_service.requires_approval,
            }
        )

    return result


# Staff with Services (comprehensive view)
@router.get("/{staff_uuid}/with-services", response_model=StaffWithServices)
async def get_staff_with_services(
    staff_uuid: UUID,
    db: AsyncSession = Depends(get_db),
    business_context=Depends(get_business_from_header),
    current_staff: Staff = Depends(get_current_staff),
):
    """
    Get staff member with all their service assignments and details.

    - **staff_uuid**: UUID of the staff member
    - Returns staff member with comprehensive service information
    """
    # Check permissions - staff can view their own profile, admins can view all
    if (
        current_staff.role not in [StaffRole.OWNER_ADMIN, StaffRole.FRONT_DESK]
        and current_staff.uuid != staff_uuid
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only view your own profile with services",
        )

    service = StaffManagementService(db)
    staff = await service.get_staff_by_uuid(
        staff_uuid, business_id=business_context.business_id
    )

    if not staff:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Staff member not found"
        )

    # Get staff services
    staff_services = await service.get_staff_services_by_uuid(
        staff_uuid, available_only=False
    )

    # Convert to response format
    services_data = []
    for staff_service in staff_services:
        services_data.append(
            {
                "id": staff_service.id,
                "service_id": staff_service.service_id,
                "staff_id": staff_service.staff_id,
                "override_duration_minutes": staff_service.override_duration_minutes,
                "override_price": staff_service.override_price,
                "override_buffer_before_minutes": staff_service.override_buffer_before_minutes,
                "override_buffer_after_minutes": staff_service.override_buffer_after_minutes,
                "is_available": staff_service.is_available,
                "expertise_level": staff_service.expertise_level,
                "notes": staff_service.notes,
                "requires_approval": staff_service.requires_approval,
            }
        )

    # Create response with services
    staff_with_services = StaffWithServices(
        **staff.__dict__, staff_services=services_data
    )

    return staff_with_services
