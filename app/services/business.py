from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
import structlog

from models.business import Business
from schemas.business import BusinessCreate, BusinessUpdate
from core.database import get_db

logger = structlog.get_logger(__name__)


class BusinessService:
    """Service layer for business operations."""

    async def create_business(
        self, db: AsyncSession, business_data: BusinessCreate
    ) -> Business:
        """Create a new business."""
        try:
            business_dict = business_data.dict()

            # Convert nested models to JSON
            if business_dict.get("branding"):
                business_dict["branding"] = (
                    business_dict["branding"].dict()
                    if hasattr(business_dict["branding"], "dict")
                    else business_dict["branding"]
                )
            if business_dict.get("policy"):
                business_dict["policy"] = (
                    business_dict["policy"].dict()
                    if hasattr(business_dict["policy"], "dict")
                    else business_dict["policy"]
                )

            business = Business(**business_dict)
            db.add(business)
            await db.commit()
            await db.refresh(business)

            logger.info(
                "Business created successfully",
                business_id=business.id,
                business_name=business.name,
            )
            return business

        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to create business due to integrity constraint", error=str(e)
            )
            raise ValueError("Business with this name may already exist")
        except Exception as e:
            await db.rollback()
            logger.error("Failed to create business", error=str(e))
            raise

    async def get_business(
        self, db: AsyncSession, business_id: int
    ) -> Optional[Business]:
        """Get business by ID."""
        try:
            result = await db.execute(
                select(Business).where(Business.id == business_id)
            )
            business = result.scalar_one_or_none()

            if not business:
                logger.warning("Business not found", business_id=business_id)

            return business

        except Exception as e:
            logger.error(
                "Failed to get business", business_id=business_id, error=str(e)
            )
            raise

    async def get_businesses(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True,
    ) -> List[Business]:
        """Get list of businesses with pagination."""
        try:
            query = select(Business)

            if active_only:
                query = query.where(Business.is_active == True)

            query = query.offset(skip).limit(limit).order_by(Business.created_at.desc())

            result = await db.execute(query)
            businesses = result.scalars().all()

            logger.info(
                "Retrieved businesses", count=len(businesses), skip=skip, limit=limit
            )
            return list(businesses)

        except Exception as e:
            logger.error("Failed to get businesses", error=str(e))
            raise

    async def update_business(
        self, db: AsyncSession, business_id: int, business_update: BusinessUpdate
    ) -> Optional[Business]:
        """Update business information."""
        try:
            # Get existing business
            business = await self.get_business(db, business_id)
            if not business:
                return None

            # Prepare update data
            update_data = business_update.dict(exclude_unset=True)

            # Convert nested models to JSON
            if "branding" in update_data and update_data["branding"]:
                update_data["branding"] = (
                    update_data["branding"].dict()
                    if hasattr(update_data["branding"], "dict")
                    else update_data["branding"]
                )
            if "policy" in update_data and update_data["policy"]:
                update_data["policy"] = (
                    update_data["policy"].dict()
                    if hasattr(update_data["policy"], "dict")
                    else update_data["policy"]
                )

            if update_data:
                await db.execute(
                    update(Business)
                    .where(Business.id == business_id)
                    .values(**update_data)
                )
                await db.commit()
                await db.refresh(business)

                logger.info(
                    "Business updated successfully",
                    business_id=business_id,
                    updated_fields=list(update_data.keys()),
                )

            return business

        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to update business due to integrity constraint",
                business_id=business_id,
                error=str(e),
            )
            raise ValueError("Update failed due to constraint violation")
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to update business", business_id=business_id, error=str(e)
            )
            raise

    async def delete_business(
        self, db: AsyncSession, business_id: int, soft_delete: bool = True
    ) -> bool:
        """Delete business (soft delete by default)."""
        try:
            business = await self.get_business(db, business_id)
            if not business:
                return False

            if soft_delete:
                # Soft delete - mark as inactive
                await db.execute(
                    update(Business)
                    .where(Business.id == business_id)
                    .values(is_active=False)
                )
                logger.info("Business soft deleted", business_id=business_id)
            else:
                # Hard delete
                await db.execute(delete(Business).where(Business.id == business_id))
                logger.info("Business hard deleted", business_id=business_id)

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to delete business", business_id=business_id, error=str(e)
            )
            raise

    async def activate_business(
        self, db: AsyncSession, business_id: int
    ) -> Optional[Business]:
        """Reactivate a soft-deleted business."""
        try:
            business = await self.get_business(db, business_id)
            if not business:
                return None

            if business.is_active:
                logger.warning("Business is already active", business_id=business_id)
                return business

            await db.execute(
                update(Business)
                .where(Business.id == business_id)
                .values(is_active=True)
            )
            await db.commit()
            await db.refresh(business)

            logger.info("Business reactivated", business_id=business_id)
            return business

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to activate business", business_id=business_id, error=str(e)
            )
            raise


business_service = BusinessService()
