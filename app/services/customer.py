from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
import structlog
from uuid import UUID, uuid4
import csv
import io
import base64
from datetime import date, datetime

from app.models.customer import Customer, CustomerStatus
from app.models.appointment import Appointment
from app.schemas.customer import (
    CustomerCreate,
    CustomerUpdate,
    CustomerSearch,
    CustomerStats,
    CustomerCSVImport,
    CustomerCSVImportResponse,
)

logger = structlog.get_logger(__name__)


class CustomerService:
    """Service layer for customer operations with CRM functionality."""

    async def create_customer(
        self, db: AsyncSession, customer_data: CustomerCreate, business_id: int
    ) -> Customer:
        """Create a new customer."""
        try:
            # Check for duplicate email if email is provided
            if customer_data.email:
                existing_customer = await db.execute(
                    select(Customer).where(
                        and_(
                            Customer.email == customer_data.email,
                            Customer.business_id == business_id,
                        )
                    )
                )
                if existing_customer.scalar_one_or_none():
                    raise ValueError(
                        "Customer with this email already exists in this business"
                    )

            customer_dict = customer_data.dict(exclude={"business_id"})
            customer_dict["business_id"] = business_id

            # Convert enum to string value
            if customer_dict.get("status"):
                customer_dict["status"] = customer_dict["status"].value
            if customer_dict.get("gender"):
                customer_dict["gender"] = customer_dict["gender"].value

            customer = Customer(**customer_dict)
            db.add(customer)
            await db.commit()
            await db.refresh(customer)

            logger.info(
                "Customer created successfully",
                customer_id=customer.id,
                customer_uuid=customer.uuid,
                customer_name=customer.full_name,
                business_id=business_id,
            )
            return customer

        except ValueError:
            # Re-raise ValueError (duplicate email) without logging as error
            raise
        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to create customer due to integrity constraint",
                error=str(e),
                business_id=business_id,
            )
            raise ValueError(
                "Customer with this email may already exist in this business"
            )
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to create customer", error=str(e), business_id=business_id
            )
            raise

    async def get_customer_by_uuid(
        self, db: AsyncSession, customer_uuid: UUID, business_id: int
    ) -> Optional[Customer]:
        """Get customer by UUID within a business."""
        try:
            result = await db.execute(
                select(Customer).where(
                    and_(
                        Customer.uuid == customer_uuid,
                        Customer.business_id == business_id,
                    )
                )
            )
            customer = result.scalar_one_or_none()

            if not customer:
                logger.warning(
                    "Customer not found",
                    customer_uuid=customer_uuid,
                    business_id=business_id,
                )

            return customer

        except Exception as e:
            logger.error(
                "Failed to get customer",
                customer_uuid=customer_uuid,
                business_id=business_id,
                error=str(e),
            )
            raise

    async def get_customers(
        self,
        db: AsyncSession,
        business_id: int,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[CustomerStatus] = None,
        include_inactive: bool = False,
    ) -> List[Customer]:
        """Get list of customers with pagination and filtering."""
        try:
            query = select(Customer).where(Customer.business_id == business_id)

            # Status filtering
            if status_filter:
                query = query.where(Customer.status == status_filter.value)
            elif not include_inactive:
                query = query.where(Customer.status == CustomerStatus.ACTIVE.value)

            query = query.offset(skip).limit(limit).order_by(Customer.created_at.desc())

            result = await db.execute(query)
            customers = result.scalars().all()

            logger.info(
                "Retrieved customers",
                count=len(customers),
                skip=skip,
                limit=limit,
                business_id=business_id,
            )
            return list(customers)

        except Exception as e:
            logger.error(
                "Failed to get customers", business_id=business_id, error=str(e)
            )
            raise

    async def search_customers(
        self,
        db: AsyncSession,
        business_id: int,
        search_params: CustomerSearch,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[List[Customer], int]:
        """Search customers with advanced filtering."""
        try:
            query = select(Customer).where(Customer.business_id == business_id)
            count_query = select(func.count(Customer.id)).where(
                Customer.business_id == business_id
            )

            # Text search across name, email, phone
            if search_params.query:
                search_term = f"%{search_params.query.lower()}%"
                search_conditions = or_(
                    func.lower(Customer.first_name).like(search_term),
                    func.lower(Customer.last_name).like(search_term),
                    func.lower(Customer.email).like(search_term),
                    Customer.phone.like(search_term),
                    Customer.alternative_phone.like(search_term),
                )
                query = query.where(search_conditions)
                count_query = count_query.where(search_conditions)

            # Status filter
            if search_params.status:
                query = query.where(Customer.status == search_params.status.value)
                count_query = count_query.where(
                    Customer.status == search_params.status.value
                )

            # VIP filter
            if search_params.is_vip is not None:
                query = query.where(Customer.is_vip == search_params.is_vip)
                count_query = count_query.where(Customer.is_vip == search_params.is_vip)

            # Location filters
            if search_params.city:
                query = query.where(
                    func.lower(Customer.city).like(f"%{search_params.city.lower()}%")
                )
                count_query = count_query.where(
                    func.lower(Customer.city).like(f"%{search_params.city.lower()}%")
                )

            if search_params.state:
                query = query.where(
                    func.lower(Customer.state).like(f"%{search_params.state.lower()}%")
                )
                count_query = count_query.where(
                    func.lower(Customer.state).like(f"%{search_params.state.lower()}%")
                )

            # Contact info filters
            if search_params.has_email is not None:
                if search_params.has_email:
                    query = query.where(Customer.email.isnot(None))
                    count_query = count_query.where(Customer.email.isnot(None))
                else:
                    query = query.where(Customer.email.is_(None))
                    count_query = count_query.where(Customer.email.is_(None))

            if search_params.has_phone is not None:
                if search_params.has_phone:
                    query = query.where(
                        or_(
                            Customer.phone.isnot(None),
                            Customer.alternative_phone.isnot(None),
                        )
                    )
                    count_query = count_query.where(
                        or_(
                            Customer.phone.isnot(None),
                            Customer.alternative_phone.isnot(None),
                        )
                    )
                else:
                    query = query.where(
                        and_(
                            Customer.phone.is_(None),
                            Customer.alternative_phone.is_(None),
                        )
                    )
                    count_query = count_query.where(
                        and_(
                            Customer.phone.is_(None),
                            Customer.alternative_phone.is_(None),
                        )
                    )

            # Date filters
            if search_params.created_after:
                query = query.where(
                    func.date(Customer.created_at) >= search_params.created_after
                )
                count_query = count_query.where(
                    func.date(Customer.created_at) >= search_params.created_after
                )

            if search_params.created_before:
                query = query.where(
                    func.date(Customer.created_at) <= search_params.created_before
                )
                count_query = count_query.where(
                    func.date(Customer.created_at) <= search_params.created_before
                )

            if search_params.last_visit_after:
                query = query.where(
                    Customer.last_visit_date >= search_params.last_visit_after
                )
                count_query = count_query.where(
                    Customer.last_visit_date >= search_params.last_visit_after
                )

            if search_params.last_visit_before:
                query = query.where(
                    Customer.last_visit_date <= search_params.last_visit_before
                )
                count_query = count_query.where(
                    Customer.last_visit_date <= search_params.last_visit_before
                )

            # Visit and spending filters
            if search_params.min_visits is not None:
                query = query.where(Customer.total_visits >= search_params.min_visits)
                count_query = count_query.where(
                    Customer.total_visits >= search_params.min_visits
                )

            if search_params.max_visits is not None:
                query = query.where(Customer.total_visits <= search_params.max_visits)
                count_query = count_query.where(
                    Customer.total_visits <= search_params.max_visits
                )

            if search_params.min_spent is not None:
                min_cents = int(search_params.min_spent * 100)
                query = query.where(Customer.total_spent >= min_cents)
                count_query = count_query.where(Customer.total_spent >= min_cents)

            if search_params.max_spent is not None:
                max_cents = int(search_params.max_spent * 100)
                query = query.where(Customer.total_spent <= max_cents)
                count_query = count_query.where(Customer.total_spent <= max_cents)

            # Risk level filter (computed field requires complex logic)
            if search_params.risk_level:
                if search_params.risk_level == "high":
                    query = query.where(Customer.no_show_count >= 3)
                    count_query = count_query.where(Customer.no_show_count >= 3)
                elif search_params.risk_level == "medium":
                    query = query.where(
                        and_(
                            Customer.no_show_count < 3,
                            or_(
                                Customer.no_show_count >= 1,
                                Customer.cancelled_appointment_count >= 3,
                            ),
                        )
                    )
                    count_query = count_query.where(
                        and_(
                            Customer.no_show_count < 3,
                            or_(
                                Customer.no_show_count >= 1,
                                Customer.cancelled_appointment_count >= 3,
                            ),
                        )
                    )
                elif search_params.risk_level == "low":
                    query = query.where(
                        and_(
                            Customer.no_show_count == 0,
                            Customer.cancelled_appointment_count < 3,
                        )
                    )
                    count_query = count_query.where(
                        and_(
                            Customer.no_show_count == 0,
                            Customer.cancelled_appointment_count < 3,
                        )
                    )

            # Get total count
            total_result = await db.execute(count_query)
            total = total_result.scalar()

            # Get paginated results
            query = query.offset(skip).limit(limit).order_by(Customer.created_at.desc())
            result = await db.execute(query)
            customers = result.scalars().all()

            logger.info(
                "Customer search completed",
                results_count=len(customers),
                total_matches=total,
                business_id=business_id,
            )
            return list(customers), total

        except Exception as e:
            logger.error(
                "Failed to search customers", business_id=business_id, error=str(e)
            )
            raise

    async def update_customer(
        self,
        db: AsyncSession,
        customer_uuid: UUID,
        customer_update: CustomerUpdate,
        business_id: int,
    ) -> Optional[Customer]:
        """Update customer information by UUID."""
        try:
            customer = await self.get_customer_by_uuid(db, customer_uuid, business_id)
            if not customer:
                return None

            update_data = customer_update.dict(exclude_unset=True)

            # Convert enums to string values
            if "status" in update_data and update_data["status"]:
                update_data["status"] = update_data["status"].value
            if "gender" in update_data and update_data["gender"]:
                update_data["gender"] = update_data["gender"].value

            if update_data:
                await db.execute(
                    update(Customer)
                    .where(
                        and_(
                            Customer.uuid == customer_uuid,
                            Customer.business_id == business_id,
                        )
                    )
                    .values(**update_data)
                )
                await db.commit()
                await db.refresh(customer)

                logger.info(
                    "Customer updated successfully",
                    customer_uuid=customer_uuid,
                    business_id=business_id,
                    updated_fields=list(update_data.keys()),
                )

            return customer

        except IntegrityError as e:
            await db.rollback()
            logger.error(
                "Failed to update customer due to integrity constraint",
                customer_uuid=customer_uuid,
                business_id=business_id,
                error=str(e),
            )
            raise ValueError("Update failed due to constraint violation")
        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to update customer",
                customer_uuid=customer_uuid,
                business_id=business_id,
                error=str(e),
            )
            raise

    async def delete_customer(
        self,
        db: AsyncSession,
        customer_uuid: UUID,
        business_id: int,
        soft_delete: bool = True,
    ) -> bool:
        """Delete customer by UUID."""
        try:
            customer = await self.get_customer_by_uuid(db, customer_uuid, business_id)
            if not customer:
                return False

            if soft_delete:
                # Soft delete - mark as inactive
                await db.execute(
                    update(Customer)
                    .where(
                        and_(
                            Customer.uuid == customer_uuid,
                            Customer.business_id == business_id,
                        )
                    )
                    .values(status=CustomerStatus.INACTIVE.value)
                )
                logger.info(
                    "Customer soft deleted",
                    customer_uuid=customer_uuid,
                    business_id=business_id,
                )
            else:
                # Hard delete
                await db.execute(
                    delete(Customer).where(
                        and_(
                            Customer.uuid == customer_uuid,
                            Customer.business_id == business_id,
                        )
                    )
                )
                logger.info(
                    "Customer hard deleted",
                    customer_uuid=customer_uuid,
                    business_id=business_id,
                )

            await db.commit()
            return True

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to delete customer",
                customer_uuid=customer_uuid,
                business_id=business_id,
                error=str(e),
            )
            raise

    async def get_customer_stats(
        self, db: AsyncSession, business_id: int
    ) -> CustomerStats:
        """Get customer statistics for a business."""
        try:
            # Basic counts
            total_customers_result = await db.execute(
                select(func.count(Customer.id)).where(
                    Customer.business_id == business_id
                )
            )
            total_customers = total_customers_result.scalar() or 0

            active_customers_result = await db.execute(
                select(func.count(Customer.id)).where(
                    and_(
                        Customer.business_id == business_id,
                        Customer.status == CustomerStatus.ACTIVE.value,
                    )
                )
            )
            active_customers = active_customers_result.scalar() or 0

            inactive_customers_result = await db.execute(
                select(func.count(Customer.id)).where(
                    and_(
                        Customer.business_id == business_id,
                        Customer.status == CustomerStatus.INACTIVE.value,
                    )
                )
            )
            inactive_customers = inactive_customers_result.scalar() or 0

            blocked_customers_result = await db.execute(
                select(func.count(Customer.id)).where(
                    and_(
                        Customer.business_id == business_id,
                        Customer.status == CustomerStatus.BLOCKED.value,
                    )
                )
            )
            blocked_customers = blocked_customers_result.scalar() or 0

            vip_customers_result = await db.execute(
                select(func.count(Customer.id)).where(
                    and_(Customer.business_id == business_id, Customer.is_vip == True)
                )
            )
            vip_customers = vip_customers_result.scalar() or 0

            # New customers this month
            from datetime import datetime

            current_month_start = datetime.now().replace(
                day=1, hour=0, minute=0, second=0, microsecond=0
            )

            new_customers_result = await db.execute(
                select(func.count(Customer.id)).where(
                    and_(
                        Customer.business_id == business_id,
                        Customer.created_at >= current_month_start,
                    )
                )
            )
            new_customers_this_month = new_customers_result.scalar() or 0

            # Customers with appointments
            customers_with_appointments_result = await db.execute(
                select(func.count(func.distinct(Appointment.customer_id))).where(
                    and_(
                        Appointment.business_id == business_id,
                        Customer.id == Appointment.customer_id,
                    )
                )
            )
            customers_with_appointments = (
                customers_with_appointments_result.scalar() or 0
            )

            # High risk customers
            high_risk_customers_result = await db.execute(
                select(func.count(Customer.id)).where(
                    and_(
                        Customer.business_id == business_id, Customer.no_show_count >= 3
                    )
                )
            )
            high_risk_customers = high_risk_customers_result.scalar() or 0

            # Financial stats
            total_value_result = await db.execute(
                select(func.sum(Customer.total_spent)).where(
                    Customer.business_id == business_id
                )
            )
            total_customer_value_cents = total_value_result.scalar() or 0
            total_customer_value = total_customer_value_cents / 100.0

            avg_value_result = await db.execute(
                select(func.avg(Customer.total_spent)).where(
                    and_(Customer.business_id == business_id, Customer.total_spent > 0)
                )
            )
            avg_lifetime_value_cents = avg_value_result.scalar() or 0
            average_lifetime_value = (
                float(avg_lifetime_value_cents) / 100.0
                if avg_lifetime_value_cents
                else 0.0
            )

            return CustomerStats(
                total_customers=total_customers,
                active_customers=active_customers,
                inactive_customers=inactive_customers,
                blocked_customers=blocked_customers,
                vip_customers=vip_customers,
                new_customers_this_month=new_customers_this_month,
                customers_with_appointments=customers_with_appointments,
                high_risk_customers=high_risk_customers,
                average_lifetime_value=average_lifetime_value,
                total_customer_value=total_customer_value,
            )

        except Exception as e:
            logger.error(
                "Failed to get customer stats", business_id=business_id, error=str(e)
            )
            raise

    async def import_customers_from_csv(
        self, db: AsyncSession, business_id: int, import_data: CustomerCSVImport
    ) -> CustomerCSVImportResponse:
        """Import customers from CSV data."""
        try:
            import_id = str(uuid4())

            # Decode CSV data
            csv_content = base64.b64decode(import_data.file_data).decode("utf-8")
            csv_reader = csv.DictReader(io.StringIO(csv_content))

            total_records = 0
            imported_records = 0
            updated_records = 0
            failed_records = 0
            errors = []
            warnings = []

            for row_num, row in enumerate(
                csv_reader, start=2
            ):  # Start at 2 to account for header
                total_records += 1

                try:
                    # Map CSV columns to Customer fields based on mapping configuration
                    customer_data = {}
                    for csv_column, customer_field in import_data.mapping.items():
                        if csv_column in row and customer_field:
                            value = row[csv_column].strip()
                            if value:  # Only add non-empty values
                                customer_data[customer_field] = value

                    # Required fields validation
                    if (
                        "first_name" not in customer_data
                        or "last_name" not in customer_data
                    ):
                        errors.append(
                            {
                                "row": row_num,
                                "error": "Missing required fields: first_name and last_name",
                            }
                        )
                        failed_records += 1
                        continue

                    # Check for existing customer if update_existing or skip_duplicates is enabled
                    existing_customer = None
                    if customer_data.get("email"):
                        result = await db.execute(
                            select(Customer).where(
                                and_(
                                    Customer.business_id == business_id,
                                    Customer.email == customer_data["email"],
                                )
                            )
                        )
                        existing_customer = result.scalar_one_or_none()

                    if existing_customer:
                        if (
                            import_data.skip_duplicates
                            and not import_data.update_existing
                        ):
                            warnings.append(
                                {
                                    "row": row_num,
                                    "warning": f'Skipping duplicate customer: {customer_data["email"]}',
                                }
                            )
                            continue
                        elif import_data.update_existing:
                            # Update existing customer
                            update_data = {
                                k: v for k, v in customer_data.items() if k != "email"
                            }
                            if update_data:
                                await db.execute(
                                    update(Customer)
                                    .where(Customer.id == existing_customer.id)
                                    .values(**update_data, source="csv_import")
                                )
                                updated_records += 1
                                continue

                    # Create new customer
                    customer_data["business_id"] = business_id
                    customer_data["source"] = "csv_import"

                    # Handle special fields
                    if "date_of_birth" in customer_data:
                        try:
                            customer_data["date_of_birth"] = datetime.strptime(
                                customer_data["date_of_birth"], "%Y-%m-%d"
                            ).date()
                        except ValueError:
                            try:
                                customer_data["date_of_birth"] = datetime.strptime(
                                    customer_data["date_of_birth"], "%m/%d/%Y"
                                ).date()
                            except ValueError:
                                warnings.append(
                                    {
                                        "row": row_num,
                                        "warning": f'Invalid date format for date_of_birth: {customer_data["date_of_birth"]}',
                                    }
                                )
                                del customer_data["date_of_birth"]

                    # Handle boolean fields
                    for bool_field in [
                        "is_vip",
                        "email_notifications",
                        "sms_notifications",
                        "marketing_emails",
                        "marketing_sms",
                    ]:
                        if bool_field in customer_data:
                            value = customer_data[bool_field].lower()
                            customer_data[bool_field] = value in [
                                "true",
                                "1",
                                "yes",
                                "y",
                            ]

                    customer = Customer(**customer_data)
                    db.add(customer)
                    imported_records += 1

                except Exception as row_error:
                    errors.append({"row": row_num, "error": str(row_error)})
                    failed_records += 1

            # Commit all changes
            await db.commit()

            logger.info(
                "CSV import completed",
                import_id=import_id,
                business_id=business_id,
                total_records=total_records,
                imported_records=imported_records,
                updated_records=updated_records,
                failed_records=failed_records,
            )

            return CustomerCSVImportResponse(
                import_id=import_id,
                total_records=total_records,
                imported_records=imported_records,
                updated_records=updated_records,
                failed_records=failed_records,
                errors=errors,
                warnings=warnings,
            )

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to import customers from CSV",
                business_id=business_id,
                error=str(e),
            )
            raise

    async def get_customer_appointment_history(
        self, db: AsyncSession, customer_uuid: UUID, business_id: int, limit: int = 50
    ) -> List[Appointment]:
        """Get customer's appointment history."""
        try:
            customer = await self.get_customer_by_uuid(db, customer_uuid, business_id)
            if not customer:
                return []

            result = await db.execute(
                select(Appointment)
                .options(
                    selectinload(Appointment.service), selectinload(Appointment.staff)
                )
                .where(
                    and_(
                        Appointment.customer_id == customer.id,
                        Appointment.business_id == business_id,
                    )
                )
                .order_by(Appointment.scheduled_datetime.desc())
                .limit(limit)
            )

            appointments = result.scalars().all()
            return list(appointments)

        except Exception as e:
            logger.error(
                "Failed to get customer appointment history",
                customer_uuid=customer_uuid,
                business_id=business_id,
                error=str(e),
            )
            raise

    async def update_customer_visit_stats(
        self,
        db: AsyncSession,
        customer_id: int,
        visit_date: date = None,
        amount_spent: int = 0,
    ) -> None:
        """Update customer visit statistics after an appointment."""
        try:
            if visit_date is None:
                visit_date = date.today()

            # Get current customer data
            result = await db.execute(
                select(Customer).where(Customer.id == customer_id)
            )
            customer = result.scalar_one_or_none()

            if customer:
                # Update visit stats
                if customer.first_visit_date is None:
                    customer.first_visit_date = visit_date

                customer.last_visit_date = visit_date
                customer.total_visits += 1
                customer.total_spent += amount_spent
                customer.last_contacted_at = datetime.now()

                await db.commit()

                logger.info(
                    "Customer visit stats updated",
                    customer_id=customer_id,
                    total_visits=customer.total_visits,
                    total_spent=customer.total_spent,
                )

        except Exception as e:
            await db.rollback()
            logger.error(
                "Failed to update customer visit stats",
                customer_id=customer_id,
                error=str(e),
            )
            raise


customer_service = CustomerService()
