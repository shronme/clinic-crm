import structlog
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.staff import Staff, StaffRole
from app.models.business import Business
from app.core.config import settings

# Import Descope only if available
try:
    from descope import AuthException, DescopeClient

    DESCOPE_AVAILABLE = True
except ImportError:
    AuthException = Exception  # Fallback for type hints
    DescopeClient = None
    DESCOPE_AVAILABLE = False

logger = structlog.get_logger(__name__)

# Initialize Descope client (only if configured and available)
descope_client = None
if DESCOPE_AVAILABLE and settings.DESCOPE_PROJECT_ID:
    descope_client = DescopeClient(
        project_id=settings.DESCOPE_PROJECT_ID,
        management_key=settings.DESCOPE_MANAGEMENT_KEY,
    )


class AuthService:
    """Authentication service for handling user creation and management."""

    @staticmethod
    async def get_or_create_user_from_descope(
        descope_user_id: str, email: str, name: str, db: AsyncSession
    ) -> Staff:
        """
        Get existing user or create new user with business and admin role.

        Args:
            descope_user_id: Descope user ID
            email: User email
            name: User name
            db: Database session

        Returns:
            Staff: The staff member (existing or newly created)
        """
        # First, try to find existing staff by descope_user_id
        result = await db.execute(
            select(Staff).where(Staff.descope_user_id == descope_user_id)
        )
        existing_staff = result.scalar_one_or_none()

        if existing_staff:
            logger.info(
                "Found existing staff member",
                staff_id=existing_staff.id,
                descope_user_id=descope_user_id,
            )
            return existing_staff

        # If no existing staff, create new business and staff
        logger.info(
            "Creating new user with business and admin role",
            descope_user_id=descope_user_id,
            email=email,
        )

        try:
            # Create new business
            business = Business(
                name=name,  # Default business name
                email=email,
                is_active=True,
            )
            db.add(business)
            await db.flush()  # Get the business ID

            # Create new staff with OWNER_ADMIN role
            staff = Staff(
                business_id=business.id,
                name=name,
                email=email,
                descope_user_id=descope_user_id,
                role=StaffRole.OWNER_ADMIN.value,
                is_active=True,
                is_bookable=True,
            )
            db.add(staff)
            await db.flush()  # Get the staff ID

            # Update Descope user with custom attributes
            if descope_client:
                try:
                    await AuthService._update_descope_user_attributes(
                        descope_user_id, staff.id, business.id
                    )
                except Exception as e:
                    logger.error(
                        "Failed to update Descope user attributes",
                        error=str(e),
                        descope_user_id=descope_user_id,
                    )
                    # Don't fail the entire process if Descope update fails

            await db.commit()

            logger.info(
                "Successfully created new user with business",
                staff_id=staff.id,
                business_id=business.id,
                descope_user_id=descope_user_id,
            )

            return staff

        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to create user due to integrity error",
                error=str(e),
                descope_user_id=descope_user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User creation failed due to data conflict",
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to create user",
                error=str(e),
                descope_user_id=descope_user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user account",
            )

    @staticmethod
    async def _update_descope_user_attributes(
        descope_user_id: str, staff_id: int, business_id: int
    ) -> None:
        """
        Update Descope user with custom attributes (staff_id, business_id).

        Args:
            descope_user_id: Descope user ID
            staff_id: Staff ID
            business_id: Business ID
        """
        if not descope_client:
            logger.warning("Descope client not available, skipping attribute update")
            return

        try:
            # Update user with custom attributes
            descope_client.mgmt.user.update(
                login_id=descope_user_id,
                custom_attributes={
                    "staff_id": str(staff_id),
                    "business_id": str(business_id),
                },
            )

            logger.info(
                "Updated Descope user attributes",
                descope_user_id=descope_user_id,
                staff_id=staff_id,
                business_id=business_id,
            )

        except AuthException as e:
            logger.error(
                "Descope management API error",
                error=str(e),
                descope_user_id=descope_user_id,
            )
            raise
        except Exception as e:
            logger.error(
                "Unexpected error updating Descope user",
                error=str(e),
                descope_user_id=descope_user_id,
            )
            raise

    @staticmethod
    async def get_user_by_descope_id(
        descope_user_id: str, db: AsyncSession
    ) -> Staff | None:
        """
        Get staff member by Descope user ID.

        Args:
            descope_user_id: Descope user ID
            db: Database session

        Returns:
            Staff or None if not found
        """
        result = await db.execute(
            select(Staff).where(Staff.descope_user_id == descope_user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def validate_descope_token(token: str) -> dict:
        """
        Validate Descope JWT token and extract user information.

        Args:
            token: JWT token from Descope

        Returns:
            dict: User information from token

        Raises:
            HTTPException: If token is invalid
        """
        if not descope_client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service not configured",
            )

        try:
            # Validate JWT token with Descope
            # If validation succeeds, jwt_response contains the session data
            # If validation fails, an AuthException is raised
            jwt_response = descope_client.validate_session(token)

            # Extract user information from JWT
            user_info = jwt_response

            # Debug: Log all available fields in the JWT response
            logger.info(
                "JWT user info fields",
                available_keys=(
                    list(user_info.keys())
                    if isinstance(user_info, dict)
                    else "Not a dict"
                ),
                full_user_info=user_info,
            )

            descope_user_id = user_info.get("sub")  # Subject (user ID)

            # Extract email and name from nsec claim (Descope custom claims)
            nsec_claims = user_info.get("nsec", {})
            email = nsec_claims.get("email") or user_info.get("email")
            name = (
                nsec_claims.get("name")
                or user_info.get("name")
                or user_info.get("given_name")
                or user_info.get("preferred_username")
            )

            # Fallback to email prefix if no name is found
            if not name and email:
                name = email.split("@")[0]
            elif not name:
                name = "User"

            if not descope_user_id:
                logger.error("No user ID found in JWT token")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token format",
                )

            return {
                "descope_user_id": descope_user_id,
                "email": email,
                "name": name,
                "claims": user_info,
            }

        except AuthException as e:
            logger.error("Descope authentication error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication failed",
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Unexpected authentication error", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication service error",
            )
