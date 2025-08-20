from datetime import datetime, date, timedelta, time
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import and_, or_, func, select
from fastapi import HTTPException, status

from app.models.staff import Staff, StaffRole
from app.models.working_hours import WorkingHours, WeekDay, OwnerType
from app.models.time_off import TimeOff, TimeOffStatus, TimeOffType
from app.models.availability_override import AvailabilityOverride, OverrideType
from app.models.staff_service import StaffService
from app.schemas.staff import (
    StaffCreate,
    StaffUpdate,
    WorkingHoursCreate,
    WorkingHoursUpdate,
    TimeOffCreate,
    TimeOffUpdate,
    AvailabilityOverrideCreate,
    AvailabilityOverrideUpdate,
    StaffAvailabilityQuery,
    StaffAvailabilitySlot,
    StaffAvailabilityResponse,
)


class StaffManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Staff CRUD Operations
    async def create_staff(
        self, staff_data: StaffCreate, created_by_staff_id: int
    ) -> Staff:
        """Create a new staff member."""
        # Validate unique email within business
        if staff_data.email:
            existing_query = select(Staff).where(
                and_(
                    Staff.business_id == staff_data.business_id,
                    Staff.email == staff_data.email,
                    Staff.is_active == True,
                )
            )
            existing_result = await self.db.execute(existing_query)
            existing = existing_result.scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists for this business",
                )

        staff = Staff(**staff_data.dict())
        self.db.add(staff)
        await self.db.commit()
        await self.db.refresh(staff)

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

    async def list_staff(
        self, business_id: int, include_inactive: bool = False
    ) -> List[Staff]:
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
            query = query.where(Staff.is_active == True)

        query = query.order_by(Staff.display_order, Staff.name)
        result = await self.db.execute(query)
        return result.scalars().all()

    async def update_staff(
        self, staff_id: int, staff_data: StaffUpdate, business_id: Optional[int] = None
    ) -> Optional[Staff]:
        """Update staff information."""
        query = select(Staff)
        if business_id:
            query = query.where(Staff.business_id == business_id)

        query = query.where(Staff.id == staff_id)
        result = await self.db.execute(query)
        staff = result.scalar_one_or_none()

        if not staff:
            return None

        # Validate unique email if being updated
        if staff_data.email and staff_data.email != staff.email:
            existing_query = select(Staff).where(
                and_(
                    Staff.business_id == staff.business_id,
                    Staff.email == staff_data.email,
                    Staff.id != staff_id,
                    Staff.is_active == True,
                )
            )
            existing_result = await self.db.execute(existing_query)
            existing = existing_result.scalar_one_or_none()

            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already exists for this business",
                )

        update_data = staff_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(staff, field, value)

        await self.db.commit()
        await self.db.refresh(staff)

        # Reload staff with relationships
        return await self.get_staff(staff_id, business_id)

    async def delete_staff(
        self, staff_id: int, business_id: Optional[int] = None
    ) -> bool:
        """Soft delete staff (set inactive)."""
        query = select(Staff)
        if business_id:
            query = query.where(Staff.business_id == business_id)

        query = query.where(Staff.id == staff_id)
        result = await self.db.execute(query)
        staff = result.scalar_one_or_none()

        if not staff:
            return False

        staff.is_active = False
        staff.is_bookable = False
        await self.db.commit()
        return True

    # Working Hours Management
    async def set_staff_working_hours(
        self, staff_id: int, working_hours: List[WorkingHoursCreate]
    ) -> List[WorkingHours]:
        """Set working hours for staff (replaces existing)."""
        staff = await self.get_staff(staff_id)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        # Remove existing working hours
        delete_query = select(WorkingHours).where(
            and_(
                WorkingHours.owner_type == OwnerType.STAFF,
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
            hours = WorkingHours(
                owner_type=OwnerType.STAFF, owner_id=staff_id, **hours_data.dict()
            )
            self.db.add(hours)
            new_hours.append(hours)

        await self.db.commit()
        for hours in new_hours:
            await self.db.refresh(hours)

        return new_hours

    async def get_staff_working_hours(
        self, staff_id: int, active_only: bool = True
    ) -> List[WorkingHours]:
        """Get working hours for staff."""
        query = select(WorkingHours).where(
            and_(
                WorkingHours.owner_type == OwnerType.STAFF,
                WorkingHours.owner_id == staff_id,
            )
        )

        if active_only:
            query = query.where(WorkingHours.is_active == True)

        query = query.order_by(WorkingHours.weekday)
        result = await self.db.execute(query)
        return result.scalars().all()

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
                TimeOff.status.in_([TimeOffStatus.PENDING, TimeOffStatus.APPROVED]),
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

        time_off = TimeOff(
            owner_type="STAFF", owner_id=staff_id, **time_off_data.dict()
        )
        self.db.add(time_off)
        await self.db.commit()
        await self.db.refresh(time_off)
        return time_off

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

        if time_off.status != TimeOffStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Can only approve pending requests",
            )

        time_off.status = TimeOffStatus.APPROVED
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

        if time_off.status != TimeOffStatus.PENDING:
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

    async def get_staff_time_offs(
        self,
        staff_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> List[TimeOff]:
        """Get time-offs for staff within date range."""
        query = select(TimeOff).where(
            and_(TimeOff.owner_type == "STAFF", TimeOff.owner_id == staff_id)
        )

        if start_date:
            query = query.where(
                TimeOff.end_datetime >= datetime.combine(start_date, time.min)
            )
        if end_date:
            query = query.where(
                TimeOff.start_datetime <= datetime.combine(end_date, time.max)
            )

        query = query.order_by(TimeOff.start_datetime)
        result = await self.db.execute(query)
        return result.scalars().all()

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
            **override_data.dict(), created_by_staff_id=created_by_staff_id
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
    ) -> List[AvailabilityOverride]:
        """Get availability overrides for staff."""
        query = select(AvailabilityOverride).where(
            and_(
                AvailabilityOverride.staff_id == staff_id,
                AvailabilityOverride.is_active == True,
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

    # Availability Calculation
    async def calculate_staff_availability(
        self, availability_query: StaffAvailabilityQuery, staff_id: int
    ) -> StaffAvailabilityResponse:
        """Calculate comprehensive staff availability."""
        staff = await self.get_staff(staff_id)
        if not staff or not staff.is_active or not staff.is_bookable:
            return StaffAvailabilityResponse(
                staff_id=staff_id,
                query_period=availability_query,
                available_slots=[],
                unavailable_periods=[],
                working_hours_summary=[],
            )

        # Get working hours
        working_hours = await self.get_staff_working_hours(staff_id)

        # Get time-offs in the period
        time_offs = []
        if availability_query.include_time_offs:
            time_offs = await self.get_staff_time_offs(
                staff_id,
                availability_query.start_datetime.date(),
                availability_query.end_datetime.date(),
            )
            time_offs = [to for to in time_offs if to.status == TimeOffStatus.APPROVED]

        # Get availability overrides
        overrides = []
        if availability_query.include_overrides:
            overrides = await self.get_staff_availability_overrides(
                staff_id,
                availability_query.start_datetime.date(),
                availability_query.end_datetime.date(),
            )

        # Calculate availability slots
        available_slots = self._calculate_availability_slots(
            availability_query.start_datetime,
            availability_query.end_datetime,
            working_hours,
            time_offs,
            overrides,
        )

        # Build unavailable periods info
        unavailable_periods = []
        for time_off in time_offs:
            unavailable_periods.append(
                {
                    "type": "time_off",
                    "start_datetime": time_off.start_datetime,
                    "end_datetime": time_off.end_datetime,
                    "reason": time_off.reason,
                    "time_off_type": time_off.type.value,
                }
            )

        # Build working hours summary
        working_hours_summary = []
        for wh in working_hours:
            summary = {
                "weekday": wh.weekday.name,
                "start_time": wh.start_time,
                "end_time": wh.end_time,
                "duration_minutes": wh.duration_minutes,
            }
            if wh.break_start_time and wh.break_end_time:
                summary["break_start_time"] = wh.break_start_time
                summary["break_end_time"] = wh.break_end_time
            working_hours_summary.append(summary)

        return StaffAvailabilityResponse(
            staff_id=staff_id,
            query_period=availability_query,
            available_slots=available_slots,
            unavailable_periods=unavailable_periods,
            working_hours_summary=working_hours_summary,
        )

    def _calculate_availability_slots(
        self,
        start_dt: datetime,
        end_dt: datetime,
        working_hours: List[WorkingHours],
        time_offs: List[TimeOff],
        overrides: List[AvailabilityOverride],
    ) -> List[StaffAvailabilitySlot]:
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
        staff = await self.get_staff(staff_id)
        if not staff:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Staff not found"
            )

        # Check if mapping already exists
        existing_query = select(StaffService).where(
            and_(
                StaffService.staff_id == staff_id, StaffService.service_id == service_id
            )
        )
        existing_result = await self.db.execute(existing_query)
        existing = existing_result.scalar_one_or_none()

        if existing:
            # Update existing mapping
            for key, value in overrides.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
        else:
            # Create new mapping
            existing = StaffService(
                staff_id=staff_id, service_id=service_id, **overrides
            )
            self.db.add(existing)

        await self.db.commit()
        await self.db.refresh(existing)
        return existing

    async def remove_service_from_staff(self, staff_id: int, service_id: int) -> bool:
        """Remove service assignment from staff."""
        query = select(StaffService).where(
            and_(
                StaffService.staff_id == staff_id, StaffService.service_id == service_id
            )
        )
        result = await self.db.execute(query)
        mapping = result.scalar_one_or_none()

        if mapping:
            await self.db.delete(mapping)
            await self.db.commit()
            return True
        return False

    async def get_staff_services(
        self, staff_id: int, available_only: bool = True
    ) -> List[StaffService]:
        """Get all services assigned to staff."""
        query = select(StaffService).where(StaffService.staff_id == staff_id)

        if available_only:
            query = query.where(StaffService.is_available == True)

        result = await self.db.execute(query)
        return result.scalars().all()

    # Permission and Access Control
    async def can_staff_access_resource(
        self, staff_id: int, resource_type: str, resource_id: int, action: str
    ) -> bool:
        """Check if staff can access a specific resource."""
        staff = await self.get_staff(staff_id)
        if not staff or not staff.is_active:
            return False

        # Owner/Admin can access everything in their business
        if staff.role == StaffRole.OWNER_ADMIN:
            return True

        # Staff can access their own resources
        if resource_type == "staff" and resource_id == staff_id:
            return action in ["read", "update"]

        # Add more granular permissions as needed
        return False
