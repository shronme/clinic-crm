from datetime import date, datetime, time, timedelta
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.availability_override import AvailabilityOverride, OverrideType
from app.models.staff import Staff, StaffRole
from app.models.staff_service import StaffService
from app.models.time_off import TimeOff, TimeOffStatus
from app.models.working_hours import OwnerType, WeekDay, WorkingHours
from app.schemas.staff import (
    AvailabilityOverrideCreate,
    StaffAvailabilityQuery,
    StaffAvailabilityResponse,
    StaffAvailabilitySlot,
    StaffCreate,
    StaffUpdate,
    TimeOffCreate,
    WorkingHoursCreate,
)
from app.services.service import ServiceManagementService

# Import Descope client for user provisioning
try:
    from descope import DescopeClient
    from app.core.config import settings

    # Initialize Descope client if available
    descope_client = None
    if settings.DESCOPE_PROJECT_ID and settings.DESCOPE_MANAGEMENT_KEY:
        descope_client = DescopeClient(
            project_id=settings.DESCOPE_PROJECT_ID,
            management_key=settings.DESCOPE_MANAGEMENT_KEY,
        )
except ImportError:
    descope_client = None


class StaffManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Staff CRUD Operations
    async def create_staff(
        self, staff_data: StaffCreate, created_by_staff_id: int
    ) -> Staff:
        """Create a new staff member with Descope user provisioning."""
        # Validate unique email within business
        if staff_data.email:
            existing_query = select(Staff).where(
                and_(
                    Staff.business_id == staff_data.business_id,
                    Staff.email == staff_data.email,
                    Staff.is_active,
                )
            )
            existing_result = await self.db.execute(existing_query)
            existing = existing_result.scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists for this business",
                )

        # 1. Create staff in database first
        staff_dict = staff_data.model_dump()
        # Convert enum values to their string representation
        if "role" in staff_dict and hasattr(staff_dict["role"], "value"):
            staff_dict["role"] = staff_dict["role"].value
        staff = Staff(**staff_dict)
        self.db.add(staff)
        await self.db.commit()
        await self.db.refresh(staff)

        # 2. Create user in Descope with custom claims (if configured)
        if descope_client and staff_data.email:
            try:
                descope_user = descope_client.management.user.create(
                    login_id=staff_data.email,
                    email=staff_data.email,
                    name=staff_data.name,
                    custom_attributes={
                        "staff_id": str(staff.id),
                        "business_id": str(staff.business_id),
                        "role": staff_dict["role"],
                    },
                )

                # 3. Store Descope user ID in staff record
                staff.descope_user_id = descope_user["userId"]
                await self.db.commit()
                await self.db.refresh(staff)

            except Exception as e:
                # Log the error but don't fail the staff creation
                # The staff member can still be created without Descope integration
                print(
                    f"Warning: Failed to create Descope user for staff "
                    f"{staff.id}: {str(e)}"
                )
                # In production, you might want to use proper logging here

        # Return staff with loaded relationships
        return await self.get_staff(staff.id, staff.business_id)

    async def get_staff(
        self, staff_id: int, business_id: Optional[int] = None
    ) -> Optional[Staff]:
        """Get staff by ID with optional business filter."""
        query = select(Staff).options(
            selectinload(Staff.availability_overrides),
            selectinload(Staff.staff_services),
        )

        if business_id:
            query = query.where(Staff.business_id == business_id)

        query = query.where(Staff.id == staff_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_staff_by_uuid(
        self, staff_uuid: UUID, business_id: Optional[int] = None
    ) -> Optional[Staff]:
        """Get staff by UUID with optional business filter."""
        query = select(Staff).options(
            selectinload(Staff.availability_overrides),
            selectinload(Staff.staff_services),
        )

        if business_id:
            query = query.where(Staff.business_id == business_id)

        query = query.where(Staff.uuid == staff_uuid)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_staff(
        self, business_id: int, include_inactive: bool = False
    ) -> list[Staff]:
        """List all staff for a business."""
        query = (
            select(Staff)
            .options(
                selectinload(Staff.availability_overrides),
                selectinload(Staff.staff_services),
            )
            .where(Staff.business_id == business_id)
        )

        if not include_inactive:
            query = query.where(Staff.is_active)

        query = query.order_by(Staff.display_order, Staff.name)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_staff(
        self, staff_id: int, staff_data: StaffUpdate, business_id: Optional[int] = None
    ) -> Optional[Staff]:
        """Update staff member."""
        staff = await self.get_staff(staff_id, business_id)
        if not staff:
            return None

        # Update fields
        for field, value in staff_data.dict(exclude_unset=True).items():
            setattr(staff, field, value)

        await self.db.commit()
        await self.db.refresh(staff)
        return staff

    async def update_staff_by_uuid(
        self,
        staff_uuid: UUID,
        staff_data: StaffUpdate,
        business_id: Optional[int] = None,
    ) -> Optional[Staff]:
        """Update staff member by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid, business_id)
        if not staff:
            return None

        # Update fields
        for field, value in staff_data.dict(exclude_unset=True).items():
            setattr(staff, field, value)

        await self.db.commit()
        await self.db.refresh(staff)
        return staff

    async def delete_staff(
        self, staff_id: int, business_id: Optional[int] = None
    ) -> bool:
        """Soft delete (deactivate) staff member."""
        staff = await self.get_staff(staff_id, business_id)
        if not staff:
            return False

        staff.is_active = False
        await self.db.commit()
        return True

    async def delete_staff_by_uuid(
        self, staff_uuid: UUID, business_id: Optional[int] = None
    ) -> bool:
        """Soft delete (deactivate) staff member by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid, business_id)
        if not staff:
            return False

        staff.is_active = False
        await self.db.commit()
        return True

    # Working Hours Management
    async def set_staff_working_hours(
        self, staff_id: int, working_hours: list[WorkingHoursCreate]
    ) -> list[WorkingHours]:
        """Set working hours for staff (replaces existing)."""
        staff = await self.get_staff(staff_id)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        # Remove existing working hours
        delete_query = select(WorkingHours).where(
            and_(
                WorkingHours.owner_type == OwnerType.STAFF.value,
                WorkingHours.owner_id == staff_id,
            )
        )
        existing_hours = await self.db.execute(delete_query)
        existing_hours_list = existing_hours.scalars().all()

        for hours in existing_hours_list:
            await self.db.delete(hours)

        # Add new working hours
        new_hours = []
        for hours_data in working_hours:
            hours_dict = hours_data.model_dump()
            # Convert enum values to their string representation for database storage
            if "weekday" in hours_dict and hasattr(hours_dict["weekday"], "value"):
                hours_dict["weekday"] = str(hours_dict["weekday"].value)
            hours = WorkingHours(
                owner_type=OwnerType.STAFF.value, owner_id=staff_id, **hours_dict
            )
            self.db.add(hours)
            new_hours.append(hours)

        await self.db.commit()
        for hours in new_hours:
            await self.db.refresh(hours)

        # Convert weekday strings back to WeekDay enums for response serialization
        from app.models.working_hours import WeekDay

        for hours in new_hours:
            if hasattr(hours, "weekday") and isinstance(hours.weekday, str):
                try:
                    # Convert string weekday ('0', '1', etc.) back to WeekDay enum
                    hours.weekday = WeekDay(int(hours.weekday))
                except (ValueError, TypeError):
                    # If conversion fails, keep as string
                    pass

        return new_hours

    async def get_staff_working_hours(
        self, staff_id: int, active_only: bool = True
    ) -> list[WorkingHours]:
        """Get working hours for staff."""
        query = select(WorkingHours).where(
            and_(
                WorkingHours.owner_type == OwnerType.STAFF.value,
                WorkingHours.owner_id == staff_id,
            )
        )

        if active_only:
            query = query.where(WorkingHours.is_active is True)

        query = query.order_by(WorkingHours.weekday)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_staff_working_hours_by_uuid(
        self, staff_uuid: UUID, active_only: bool = True
    ) -> list[WorkingHours]:
        """Get working hours for staff by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            return []

        return await self.get_staff_working_hours(staff.id, active_only)

    async def set_staff_working_hours_by_uuid(
        self, staff_uuid: UUID, working_hours: list[WorkingHoursCreate]
    ) -> list[WorkingHours]:
        """Set working hours for staff by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        return await self.set_staff_working_hours(staff.id, working_hours)

    # Time-Off Management
    async def create_time_off(
        self, staff_id: int, time_off_data: TimeOffCreate, created_by_staff_id: int
    ) -> TimeOff:
        """Create time-off request."""
        staff = await self.get_staff(staff_id)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        # Check for overlapping time-off
        existing_overlap_query = select(TimeOff).where(
            and_(
                TimeOff.owner_type == "STAFF",
                TimeOff.owner_id == staff_id,
                TimeOff.status.in_(
                    [TimeOffStatus.PENDING.value, TimeOffStatus.APPROVED.value]
                ),
                or_(
                    and_(
                        TimeOff.start_datetime <= time_off_data.start_datetime,
                        TimeOff.end_datetime > time_off_data.start_datetime,
                    ),
                    and_(
                        TimeOff.start_datetime < time_off_data.end_datetime,
                        TimeOff.end_datetime >= time_off_data.end_datetime,
                    ),
                    and_(
                        TimeOff.start_datetime >= time_off_data.start_datetime,
                        TimeOff.end_datetime <= time_off_data.end_datetime,
                    ),
                ),
            )
        )

        existing_overlap_result = await self.db.execute(existing_overlap_query)
        existing_overlap = existing_overlap_result.scalar_one_or_none()

        if existing_overlap:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Time-off period overlaps with existing request",
            )

        time_off_dict = time_off_data.model_dump()
        # Convert enum values to their string representation for database storage
        if "type" in time_off_dict and hasattr(time_off_dict["type"], "value"):
            time_off_dict["type"] = time_off_dict["type"].value
        time_off = TimeOff(owner_type="STAFF", owner_id=staff_id, **time_off_dict)
        self.db.add(time_off)
        await self.db.commit()
        await self.db.refresh(time_off)
        return time_off

    async def create_time_off_by_uuid(
        self, staff_uuid: UUID, time_off_data: TimeOffCreate, created_by_staff_id: int
    ) -> TimeOff:
        """Create time-off request by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        return await self.create_time_off(staff.id, time_off_data, created_by_staff_id)

    async def get_staff_time_offs(
        self,
        staff_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[TimeOff]:
        """Get time-off requests for staff."""
        query = select(TimeOff).where(
            and_(
                TimeOff.owner_type == "STAFF",
                TimeOff.owner_id == staff_id,
            )
        )

        if start_date:
            query = query.where(TimeOff.start_datetime >= start_date)

        if end_date:
            query = query.where(TimeOff.end_datetime <= end_date)

        query = query.order_by(TimeOff.start_datetime)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_staff_time_offs_by_uuid(
        self,
        staff_uuid: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[TimeOff]:
        """Get time-off requests for staff by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            return []

        return await self.get_staff_time_offs(staff.id, start_date, end_date)

    async def approve_time_off(
        self,
        time_off_id: int,
        approved_by_staff_id: int,
        approval_notes: Optional[str] = None,
    ) -> TimeOff:
        """Approve time-off request."""
        query = select(TimeOff).where(TimeOff.id == time_off_id)
        result = await self.db.execute(query)
        time_off = result.scalar_one_or_none()

        if not time_off:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time-off request not found",
            )

        if time_off.status != TimeOffStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only approve pending requests",
            )

        time_off.status = TimeOffStatus.APPROVED.value
        time_off.approved_by_staff_id = approved_by_staff_id
        time_off.approved_at = datetime.utcnow()
        time_off.approval_notes = approval_notes

        await self.db.commit()
        await self.db.refresh(time_off)
        return time_off

    async def approve_time_off_by_uuid(
        self,
        time_off_uuid: UUID,
        approved_by_staff_id: int,
        approval_notes: Optional[str] = None,
    ) -> TimeOff:
        """Approve time-off request by UUID."""
        query = select(TimeOff).where(TimeOff.uuid == time_off_uuid)
        result = await self.db.execute(query)
        time_off = result.scalar_one_or_none()

        if not time_off:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time-off request not found",
            )

        if time_off.status != TimeOffStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only approve pending requests",
            )

        time_off.status = TimeOffStatus.APPROVED.value
        time_off.approved_by_staff_id = approved_by_staff_id
        time_off.approved_at = datetime.utcnow()
        time_off.approval_notes = approval_notes

        await self.db.commit()
        await self.db.refresh(time_off)
        return time_off

    async def deny_time_off(
        self,
        time_off_id: int,
        denied_by_staff_id: int,
        denial_notes: Optional[str] = None,
    ) -> TimeOff:
        """Deny time-off request."""
        query = select(TimeOff).where(TimeOff.id == time_off_id)
        result = await self.db.execute(query)
        time_off = result.scalar_one_or_none()

        if not time_off:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time-off request not found",
            )

        if time_off.status != TimeOffStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only deny pending requests",
            )

        time_off.status = TimeOffStatus.DENIED
        time_off.approved_by_staff_id = denied_by_staff_id
        time_off.approved_at = datetime.utcnow()
        time_off.approval_notes = denial_notes

        await self.db.commit()
        await self.db.refresh(time_off)
        return time_off

    async def deny_time_off_by_uuid(
        self,
        time_off_uuid: UUID,
        denied_by_staff_id: int,
        denial_notes: Optional[str] = None,
    ) -> TimeOff:
        """Deny time-off request by UUID."""
        query = select(TimeOff).where(TimeOff.uuid == time_off_uuid)
        result = await self.db.execute(query)
        time_off = result.scalar_one_or_none()

        if not time_off:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Time-off request not found",
            )

        if time_off.status != TimeOffStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only deny pending requests",
            )

        time_off.status = TimeOffStatus.DENIED
        time_off.approved_by_staff_id = denied_by_staff_id
        time_off.approved_at = datetime.utcnow()
        time_off.approval_notes = denial_notes

        await self.db.commit()
        await self.db.refresh(time_off)
        return time_off

    # Availability Override Management
    async def create_availability_override(
        self, override_data: AvailabilityOverrideCreate, created_by_staff_id: int
    ) -> AvailabilityOverride:
        """Create availability override."""
        staff = await self.get_staff(override_data.staff_id)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        override = AvailabilityOverride(
            **override_data.model_dump(), created_by_staff_id=created_by_staff_id
        )
        self.db.add(override)
        await self.db.commit()
        await self.db.refresh(override)
        return override

    async def get_staff_availability_overrides(
        self,
        staff_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[AvailabilityOverride]:
        """Get availability overrides for staff."""
        query = select(AvailabilityOverride).where(
            and_(
                AvailabilityOverride.staff_id == staff_id,
                AvailabilityOverride.is_active is True,
            )
        )

        if start_date:
            query = query.where(
                AvailabilityOverride.end_datetime
                >= datetime.combine(start_date, time.min)
            )
        if end_date:
            query = query.where(
                AvailabilityOverride.start_datetime
                <= datetime.combine(end_date, time.max)
            )

        query = query.order_by(AvailabilityOverride.start_datetime)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_staff_availability_overrides_by_uuid(
        self,
        staff_uuid: UUID,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> list[AvailabilityOverride]:
        """Get availability overrides for staff by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            return []

        return await self.get_staff_availability_overrides(
            staff.id, start_date, end_date
        )

    async def create_availability_override_by_uuid(
        self,
        staff_uuid: UUID,
        override_data: AvailabilityOverrideCreate,
        created_by_staff_id: int,
    ) -> AvailabilityOverride:
        """Create availability override by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        return await self.create_availability_override(
            AvailabilityOverrideCreate(**override_data.model_dump(), staff_id=staff.id),
            created_by_staff_id,
        )

    # Availability Calculation
    async def calculate_staff_availability(
        self, availability_query: StaffAvailabilityQuery, staff_id: int
    ) -> StaffAvailabilityResponse:
        """Calculate staff availability for a given time period."""
        # This is a placeholder implementation
        # In a real implementation, this would calculate actual availability
        # based on working hours, time-offs, overrides, and existing bookings

        available_slots = [
            StaffAvailabilitySlot(
                start_datetime=availability_query.start_datetime,
                end_datetime=availability_query.end_datetime,
                is_available=True,
                availability_type="normal",
                restrictions=None,
            )
        ]

        return StaffAvailabilityResponse(
            staff_id=staff_id,
            query_period=availability_query,
            available_slots=available_slots,
            unavailable_periods=[],
            working_hours_summary=[],
        )

    async def calculate_staff_availability_by_uuid(
        self, availability_query: StaffAvailabilityQuery, staff_uuid: UUID
    ) -> StaffAvailabilityResponse:
        """Calculate staff availability for a given time period by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        return await self.calculate_staff_availability(availability_query, staff.id)

    def _calculate_availability_slots(
        self,
        start_dt: datetime,
        end_dt: datetime,
        working_hours: list[WorkingHours],
        time_offs: list[TimeOff],
        overrides: list[AvailabilityOverride],
    ) -> list[StaffAvailabilitySlot]:
        """Internal method to calculate availability slots."""
        slots = []
        current_dt = start_dt

        while current_dt < end_dt:
            day_end = min(datetime.combine(current_dt.date(), time.max), end_dt)

            # Find working hours for this weekday
            weekday = WeekDay(current_dt.weekday())
            day_working_hours = [
                wh for wh in working_hours if wh.weekday == weekday and wh.is_active
            ]

            if day_working_hours:
                for wh in day_working_hours:
                    slot_start = max(
                        current_dt, datetime.combine(current_dt.date(), wh.start_time)
                    )
                    slot_end = min(
                        day_end, datetime.combine(current_dt.date(), wh.end_time)
                    )

                    if slot_start < slot_end:
                        # Check for time-offs that affect this slot
                        slot_available = True
                        availability_type = "normal"

                        for time_off in time_offs:
                            if time_off.overlaps_with(slot_start, slot_end):
                                slot_available = False
                                break

                        # Check for overrides
                        for override in overrides:
                            if override.overlaps_with(slot_start, slot_end):
                                if override.override_type == OverrideType.UNAVAILABLE:
                                    slot_available = False
                                elif override.override_type == OverrideType.AVAILABLE:
                                    slot_available = True
                                    availability_type = "override"
                                break

                        slots.append(
                            StaffAvailabilitySlot(
                                start_datetime=slot_start,
                                end_datetime=slot_end,
                                is_available=slot_available,
                                availability_type=availability_type,
                            )
                        )

            # Move to next day
            current_dt = datetime.combine(
                current_dt.date() + timedelta(days=1), time.min
            )

        return slots

    # Service Mapping Management
    async def assign_service_to_staff(
        self, staff_id: int, service_id: int, **overrides
    ) -> StaffService:
        """Assign a service to staff with optional overrides."""
        # Check if assignment already exists
        print(
            f"Assigning service {service_id} to staff {staff_id} with overrides: "
            f"{overrides}"
        )
        existing_query = select(StaffService).where(
            and_(
                StaffService.staff_id == staff_id, StaffService.service_id == service_id
            )
        )
        existing_result = await self.db.execute(existing_query)
        existing = existing_result.scalar_one_or_none()
        print(f"Existing: {existing}")
        if existing:
            # Update existing assignment
            for field, value in overrides.items():
                if hasattr(existing, field):
                    setattr(existing, field, value)
            await self.db.commit()
            await self.db.refresh(existing)
            return existing
        else:
            # Create new assignment
            staff_service = StaffService(
                staff_id=staff_id, service_id=service_id, **overrides
            )
            self.db.add(staff_service)
            await self.db.commit()
            await self.db.refresh(staff_service)
            return staff_service

    async def assign_service_to_staff_by_uuid(
        self, staff_uuid: UUID, service_uuid: UUID, **overrides
    ) -> StaffService:
        """Assign a service to staff by UUID with optional overrides."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        # Get the service by UUID to get its ID
        service = await ServiceManagementService.get_service_by_uuid(
            self.db, service_uuid, staff.business_id
        )
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Service not found"
            )

        return await self.assign_service_to_staff(staff.id, service.id, **overrides)

    async def remove_service_from_staff(self, staff_id: int, service_id: int) -> bool:
        """Remove service assignment from staff."""
        query = select(StaffService).where(
            and_(
                StaffService.staff_id == staff_id, StaffService.service_id == service_id
            )
        )
        result = await self.db.execute(query)
        staff_service = result.scalar_one_or_none()

        if not staff_service:
            return False

        await self.db.delete(staff_service)
        await self.db.commit()
        return True

    async def remove_service_from_staff_by_uuid(
        self, staff_uuid: UUID, service_uuid: UUID
    ) -> bool:
        """Remove service assignment from staff by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            return False

        # Get the service by UUID to get its ID
        service = await ServiceManagementService.get_service_by_uuid(
            self.db, service_uuid, staff.business_id
        )
        if not service:
            return False

        return await self.remove_service_from_staff(staff.id, service.id)

    async def get_staff_services(
        self, staff_id: int, available_only: bool = True
    ) -> list[StaffService]:
        """Get services assigned to staff."""
        query = select(StaffService).where(StaffService.staff_id == staff_id)

        if available_only:
            query = query.where(StaffService.is_available)

        query = query.order_by(StaffService.service_id)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def get_staff_services_by_uuid(
        self, staff_uuid: UUID, available_only: bool = True
    ) -> list[StaffService]:
        """Get services assigned to staff by UUID."""
        staff = await self.get_staff_by_uuid(staff_uuid)
        if not staff:
            return []

        return await self.get_staff_services(staff.id, available_only)

    # Permission and Access Control
    async def can_staff_access_resource(
        self, staff_id: int, resource_type: str, resource_id: int, action: str
    ) -> bool:
        """Check if staff can access a specific resource."""
        staff = await self.get_staff(staff_id)
        if not staff or not staff.is_active:
            return False

        # Owner/Admin can access everything in their business
        if staff.role == StaffRole.OWNER_ADMIN.value:
            return True

        # Staff can access their own resources
        if resource_type == "staff" and resource_id == staff_id:
            return action in ["read", "update"]

        # Add more granular permissions as needed
        return False
