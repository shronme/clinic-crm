# Scheduling Engine Implementation

This document describes the core scheduling engine implementation for the Barber & Beautician CRM system.

## Overview

The scheduling engine provides comprehensive availability calculation and appointment validation, considering all relevant business constraints including:

- Business working hours and breaks
- Staff working hours and breaks  
- Existing appointments and conflicts
- Time off periods and approvals
- Availability overrides (temporary schedule changes)
- Service duration and buffer times
- Lead time policies (minimum advance booking)
- Maximum advance booking policies
- Service addon duration calculations

## Architecture

### Core Components

1. **SchedulingEngineService** (`app/services/scheduling.py`)
   - Main service class containing all scheduling logic
   - Handles availability calculations and conflict detection
   - Provides appointment validation and alternative slot suggestions

2. **Scheduling Schemas** (`app/schemas/scheduling.py`)
   - Pydantic models for request/response data
   - Type-safe API contracts
   - Input validation and serialization

3. **API Endpoints** (`app/api/v1/endpoints/scheduling.py`)
   - REST API endpoints for scheduling operations
   - Comprehensive documentation and error handling
   - Support for bulk operations and advanced queries

4. **Database Models**
   - Enhanced existing models with scheduling-specific methods
   - Support for polymorphic relationships (business/staff working hours)
   - Proper indexing for performance

### Key Features

#### Staff Availability Calculation

```python
query = StaffAvailabilityQuery(
    staff_uuid="staff-uuid-1",
    start_datetime=datetime(2024, 1, 15, 9, 0),
    end_datetime=datetime(2024, 1, 15, 17, 0),
    service_uuid="service-uuid-1",  # Optional
    slot_duration_minutes=30,
    include_busy_slots=False
)

slots = scheduling_service.get_staff_availability(query)
```

#### Appointment Validation

```python
request = AppointmentValidationRequest(
    staff_uuid="staff-uuid-1",
    service_uuid="service-uuid-1", 
    requested_datetime=datetime(2024, 1, 15, 10, 0),
    addon_uuids=[]
)

response = scheduling_service.validate_appointment(request)
if not response.is_valid:
    print(f"Conflicts: {[c.message for c in response.conflicts]}")
    print(f"Alternatives: {len(response.alternative_slots)} available")
```

## API Endpoints

### Staff Availability

**GET** `/api/v1/scheduling/staff/availability`

Get available time slots for a staff member.

**Parameters:**
- `staff_uuid` (required): Staff member UUID
- `start_datetime` (required): Start of time range
- `end_datetime` (required): End of time range
- `service_uuid` (optional): Service UUID for compatibility check
- `slot_duration_minutes` (optional): Slot duration (default: 15)
- `include_busy_slots` (optional): Include unavailable slots (default: false)

### Appointment Validation

**POST** `/api/v1/scheduling/appointments/validate`

Validate if an appointment can be scheduled.

**Request Body:**
```json
{
  "staff_uuid": "staff-uuid-1",
  "service_uuid": "service-uuid-1",
  "requested_datetime": "2024-01-15T10:00:00",
  "customer_uuid": "customer-uuid-1",
  "addon_uuids": []
}
```

**Response:**
```json
{
  "is_valid": true,
  "conflicts": [],
  "alternative_slots": [],
  "total_duration_minutes": 40,
  "estimated_end_time": "2024-01-15T10:40:00"
}
```

### Business Hours

**GET** `/api/v1/scheduling/business/hours`

Get business operating hours for a specific date.

### Staff Schedule

**GET** `/api/v1/scheduling/staff/schedule`

Get comprehensive schedule information for a staff member.

### Advanced Endpoints

- **GET** `/api/v1/scheduling/staff/{staff_uuid}/conflicts` - Check for scheduling conflicts
- **GET** `/api/v1/scheduling/availability/bulk` - Bulk availability for multiple staff
- **GET** `/api/v1/scheduling/next-available` - Find next available appointment slot
- **POST** `/api/v1/scheduling/availability/reserve` - Temporarily reserve a time slot

## Conflict Detection

The scheduling engine detects various types of conflicts:

### Conflict Types

1. **EXISTING_APPOINTMENT** - Time overlaps with existing appointment
2. **TIME_OFF** - Staff has approved time off
3. **OUTSIDE_WORKING_HOURS** - Outside business or staff working hours
4. **INSUFFICIENT_BUFFER** - Not enough buffer time before/after service
5. **LEAD_TIME_VIOLATION** - Doesn't meet minimum advance booking requirement
6. **ADVANCE_BOOKING_VIOLATION** - Exceeds maximum advance booking limit
7. **AVAILABILITY_OVERRIDE** - Conflicts with availability override
8. **STAFF_UNAVAILABLE** - Staff not found or inactive

### Validation Logic

The engine performs validation in this order:

1. **Basic Validation**
   - Staff and service existence
   - Staff is active and bookable

2. **Time Constraints**
   - Business hours compliance
   - Staff working hours compliance
   - Break time avoidance

3. **Conflict Checks**
   - Existing appointment overlaps
   - Time off periods
   - Availability overrides

4. **Policy Validation**
   - Lead time requirements
   - Advance booking limits
   - Service-specific policies

## Working Hours System

The system supports flexible working hours with:

### Polymorphic Design

Working hours can be assigned to:
- **Business** - Default operating hours
- **Staff** - Individual staff schedules

### Features

- **Weekly Schedules** - Different hours for each day of week
- **Break Support** - Configurable break periods
- **Temporary Overrides** - Date range specific changes
- **Inheritance** - Staff hours can override business hours

### Database Schema

```sql
-- Working hours with polymorphic owner
CREATE TABLE working_hours (
    id SERIAL PRIMARY KEY,
    uuid UUID UNIQUE NOT NULL,
    owner_type VARCHAR NOT NULL,  -- 'business' or 'staff'
    owner_id INTEGER NOT NULL,
    weekday INTEGER NOT NULL,     -- 0=Monday, 6=Sunday
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    break_start_time TIME,
    break_end_time TIME,
    is_active BOOLEAN DEFAULT TRUE,
    effective_from TIMESTAMP WITH TIME ZONE,
    effective_until TIMESTAMP WITH TIME ZONE
);
```

## Time Off Management

Comprehensive time off system with:

### Features

- **Multiple Types** - Vacation, sick leave, personal, training, etc.
- **Approval Workflow** - Pending → Approved/Denied workflow
- **Recurring Support** - RRULE-based recurring time off
- **All-day vs Timed** - Flexible time off periods

### Time Off Types

- `VACATION` - Planned vacation time
- `SICK_LEAVE` - Illness-related absence
- `PERSONAL` - Personal time off
- `TRAINING` - Professional development
- `HOLIDAY` - Company/public holidays
- `MAINTENANCE` - Equipment/facility maintenance
- `OTHER` - Other types of absence

## Availability Overrides

Temporary schedule modifications with:

### Override Types

- **AVAILABLE** - Make staff available during normally unavailable times
- **UNAVAILABLE** - Block normally available times
- **CUSTOM_HOURS** - Custom working hours for specific periods

### Use Cases

- **Special Events** - Extended hours for special occasions
- **Emergency Coverage** - Last-minute schedule adjustments
- **Planned Closures** - Temporary unavailability
- **Training Sessions** - Block time for staff training

## Performance Considerations

### Database Optimization

- **Proper Indexing** - Indexes on frequently queried fields
- **Query Optimization** - Efficient filtering and joining
- **Batch Operations** - Bulk availability queries

### Caching Strategy

- **Business Hours** - Cache daily business hours
- **Staff Schedules** - Cache weekly staff schedules
- **Service Metadata** - Cache service duration and policies

### Scalability

- **Async Support** - Ready for async database operations
- **Horizontal Scaling** - Stateless service design
- **Load Balancing** - No session dependencies

## Testing

### Test Coverage

- **Unit Tests** - `tests/unit/test_scheduling_service.py`
- **Integration Tests** - `tests/integration/test_scheduling_api.py`
- **Mock-based Testing** - Isolated unit test without database dependencies

### Test Scenarios

- Staff availability with various constraints
- Appointment validation with conflicts
- Business hours edge cases
- Time off conflict detection
- Availability override handling
- Lead time and advance booking policies

### Running Tests

```bash
# Unit tests
python -m pytest tests/unit/test_scheduling_service.py -v

# Integration tests (requires database)
python -m pytest tests/integration/test_scheduling_api.py -v

# All scheduling tests
python -m pytest tests/ -k scheduling -v
```

## Usage Examples

### Basic Availability Check

```python
from app.services.scheduling import SchedulingEngineService
from app.schemas.scheduling import StaffAvailabilityQuery
from datetime import datetime

# Initialize service
scheduling_service = SchedulingEngineService(db_session)

# Check availability
query = StaffAvailabilityQuery(
    staff_uuid="staff-uuid-1",
    start_datetime=datetime(2024, 1, 15, 9, 0),
    end_datetime=datetime(2024, 1, 15, 17, 0),
    slot_duration_minutes=30
)

slots = scheduling_service.get_staff_availability(query)
available_slots = [s for s in slots if s.status == AvailabilityStatus.AVAILABLE]
```

### Appointment Validation

```python
from app.schemas.scheduling import AppointmentValidationRequest

request = AppointmentValidationRequest(
    staff_uuid="staff-uuid-1",
    service_uuid="service-uuid-1",
    requested_datetime=datetime(2024, 1, 15, 10, 0)
)

response = scheduling_service.validate_appointment(request)

if response.is_valid:
    print("✅ Appointment can be scheduled")
else:
    print("❌ Conflicts found:")
    for conflict in response.conflicts:
        print(f"  - {conflict.message}")
    
    print(f"📅 {len(response.alternative_slots)} alternatives available")
```

### Finding Next Available Slot

```python
# Use API endpoint
import requests

response = requests.get('/api/v1/scheduling/next-available', params={
    'staff_uuid': 'staff-uuid-1',
    'service_uuid': 'service-uuid-1',
    'max_days_ahead': 7
})

data = response.json()
if data['found']:
    slot = data['next_available_slot']
    print(f"Next available: {slot['start_datetime']}")
```

## Future Enhancements

### Planned Features

1. **Smart Scheduling**
   - AI-powered optimal slot suggestions
   - Load balancing across staff
   - Preference-based scheduling

2. **Advanced Policies**
   - Dynamic pricing based on demand
   - Cancellation and rescheduling policies
   - Group appointment handling

3. **Integration Features**
   - Calendar synchronization (Google, Outlook)
   - External booking platform integration
   - Webhook notifications

4. **Analytics**
   - Utilization tracking
   - Peak time analysis
   - Staff performance metrics

### Technical Improvements

1. **Performance**
   - Redis caching layer
   - Database query optimization
   - Async/await support

2. **Reliability**
   - Circuit breaker pattern
   - Retry mechanisms  
   - Health check endpoints

3. **Monitoring**
   - Detailed logging
   - Performance metrics
   - Error tracking

## Troubleshooting

### Common Issues

1. **No Available Slots**
   - Check business/staff working hours
   - Verify time off periods
   - Check availability overrides
   - Review lead time policies

2. **Validation Errors**
   - Ensure staff is active and bookable
   - Verify service exists and is active
   - Check business policies
   - Review time zone handling

3. **Performance Issues**
   - Review database indexes
   - Check query execution plans
   - Monitor cache hit rates
   - Analyze API response times

### Debug Mode

Enable detailed logging by setting environment variable:
```bash
export SCHEDULING_DEBUG=true
```

This will provide detailed information about:
- Availability calculation steps
- Conflict detection logic
- Database query execution
- Cache operations

## Configuration

### Environment Variables

- `SCHEDULING_DEBUG` - Enable debug logging
- `SCHEDULING_CACHE_TTL` - Cache time-to-live in seconds
- `SCHEDULING_MAX_ALTERNATIVES` - Maximum alternative slots to return
- `SCHEDULING_DEFAULT_SLOT_DURATION` - Default slot duration in minutes

### Business Policies

Configure in business model policy JSON:
```json
{
  "min_lead_time_hours": 2,
  "max_advance_booking_days": 30,
  "default_buffer_minutes": 5,
  "allow_double_booking": false,
  "weekend_booking_enabled": true
}
```

## Conclusion

The scheduling engine provides a robust, scalable foundation for appointment booking in the Barber & Beautician CRM system. It handles complex business rules while maintaining high performance and reliability.

For questions or support, refer to the test files for usage examples or contact the development team.