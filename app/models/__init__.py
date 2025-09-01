# Import all models to ensure they are registered with SQLAlchemy
from . import (
    appointment,
    availability_override,
    business,
    customer,
    note,
    notification,
    service,
    service_addon,
    service_category,
    staff,
    staff_service,
    time_off,
    working_hours,
)

__all__ = [
    "appointment",
    "availability_override",
    "business",
    "customer",
    "note",
    "notification",
    "service",
    "service_addon",
    "service_category",
    "staff",
    "staff_service",
    "time_off",
    "working_hours",
]
