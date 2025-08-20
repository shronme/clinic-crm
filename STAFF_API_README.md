# Staff API Documentation

## Overview

The Staff API provides comprehensive functionality for managing staff members, their working hours, time-off requests, availability overrides, and service assignments in the Barber & Beautician CRM system.

## Authentication

All endpoints require authentication via headers:
- `X-Staff-ID`: Current authenticated staff member ID
- `X-Business-ID`: Business context for multi-tenant operations

## Base URL

```
/api/v1/staff
```

## Endpoints

### 1. Staff CRUD Operations

#### GET / - List Staff Members
Retrieve all staff members for the business.

**Query Parameters:**
- `include_inactive` (boolean, optional): Include inactive staff members (default: false)

**Permissions:** Staff, Front Desk, Owner/Admin

**Response:** List of `StaffSummary` objects

**Example:**
```bash
GET /api/v1/staff/?include_inactive=true
Headers:
  X-Staff-ID: 2
  X-Business-ID: 1
```

#### POST / - Create Staff Member
Create a new staff member.

**Permissions:** Owner/Admin only

**Request Body:**
```json
{
  "business_id": 1,
  "name": "New Staff Member",
  "email": "newstaff@example.com",
  "phone": "123-456-7890",
  "role": "staff",
  "is_bookable": true,
  "is_active": true,
  "bio": "Experienced hairstylist"
}
```

**Response:** Created `Staff` object (201 Created)

#### GET /{staff_id} - Get Staff Member
Retrieve a specific staff member by ID.

**Permissions:** 
- Staff can view their own profile
- Front Desk/Admin can view any staff profile

**Response:** `Staff` object

#### PUT /{staff_id} - Update Staff Member
Update staff member information.

**Permissions:**
- Staff can update their own profile (limited fields)
- Front Desk/Admin can update any staff profile

**Request Body:** Partial `StaffUpdate` object

**Response:** Updated `Staff` object

#### DELETE /{staff_id} - Delete Staff Member
Soft delete (deactivate) a staff member.

**Permissions:** Owner/Admin only

**Response:** 204 No Content

**Note:** Cannot delete your own account

### 2. Working Hours Management

#### POST /{staff_id}/working-hours - Set Working Hours
Set working hours for a staff member (replaces existing).

**Permissions:**
- Staff can set their own hours
- Front Desk/Admin can set any staff hours

**Request Body:** List of `WorkingHoursCreate` objects

**Example:**
```json
[
  {
    "weekday": "monday",
    "start_time": "09:00:00",
    "end_time": "17:00:00",
    "break_start_time": "12:00:00",
    "break_end_time": "13:00:00",
    "is_active": true
  }
]
```

**Response:** List of `WorkingHours` objects

#### GET /{staff_id}/working-hours - Get Working Hours
Retrieve working hours for a staff member.

**Query Parameters:**
- `active_only` (boolean, optional): Include only active hours (default: true)

**Response:** List of `WorkingHours` objects

### 3. Time-Off Management

#### POST /{staff_id}/time-off - Create Time-Off Request
Create a time-off request for a staff member.

**Permissions:**
- Staff can create their own time-off requests
- Front Desk/Admin can create time-off for any staff

**Request Body:** `TimeOffCreate` object

**Example:**
```json
{
  "start_datetime": "2024-06-01T09:00:00",
  "end_datetime": "2024-06-03T17:00:00",
  "type": "vacation",
  "reason": "Summer vacation",
  "is_all_day": false
}
```

**Response:** Created `TimeOff` object (201 Created)

#### GET /{staff_id}/time-off - Get Time-Off Requests
Retrieve time-off requests for a staff member.

**Query Parameters:**
- `start_date` (string, optional): Start date filter (YYYY-MM-DD)
- `end_date` (string, optional): End date filter (YYYY-MM-DD)

**Response:** List of `TimeOff` objects

#### POST /time-off/{time_off_id}/approve - Approve Time-Off Request
Approve a time-off request.

**Permissions:** Owner/Admin only

**Request Body:**
```json
{
  "approval_notes": "Approved for vacation"
}
```

**Response:** Approved `TimeOff` object

#### POST /time-off/{time_off_id}/deny - Deny Time-Off Request
Deny a time-off request.

**Permissions:** Owner/Admin only

**Request Body:**
```json
{
  "denial_notes": "Denied due to staffing needs"
}
```

**Response:** Denied `TimeOff` object

### 4. Availability Override Management

#### POST /{staff_id}/availability-overrides - Create Availability Override
Create an availability override for a staff member.

**Permissions:**
- Staff can create their own overrides
- Front Desk/Admin can create overrides for any staff

**Request Body:** `AvailabilityOverrideCreate` object

**Example:**
```json
{
  "staff_id": 1,
  "override_type": "unavailable",
  "start_datetime": "2024-06-01T09:00:00",
  "end_datetime": "2024-06-01T12:00:00",
  "title": "Doctor appointment",
  "reason": "Medical checkup",
  "is_active": true,
  "allow_new_bookings": false
}
```

**Response:** Created `AvailabilityOverride` object (201 Created)

#### GET /{staff_id}/availability-overrides - Get Availability Overrides
Retrieve availability overrides for a staff member.

**Query Parameters:**
- `start_date` (string, optional): Start date filter (YYYY-MM-DD)
- `end_date` (string, optional): End date filter (YYYY-MM-DD)

**Response:** List of `AvailabilityOverride` objects

### 5. Availability Calculation

#### POST /{staff_id}/availability - Calculate Staff Availability
Calculate comprehensive staff availability for a given time period.

**Permissions:**
- Staff can check their own availability
- Front Desk/Admin can check any staff availability

**Request Body:** `StaffAvailabilityQuery` object

**Example:**
```json
{
  "start_datetime": "2024-06-03T00:00:00",
  "end_datetime": "2024-06-04T23:59:59",
  "service_ids": [1, 2],
  "include_overrides": true,
  "include_time_offs": true
}
```

**Response:** `StaffAvailabilityResponse` object with:
- Available time slots
- Unavailable periods
- Working hours summary

### 6. Service Mapping Management

#### POST /{staff_id}/services - Assign Service to Staff
Assign a service to a staff member with optional overrides.

**Permissions:** Owner/Admin only

**Request Body:** `StaffServiceOverride` object

**Example:**
```json
{
  "service_id": 1,
  "override_duration_minutes": 45,
  "override_price": 30.00,
  "override_buffer_before_minutes": 10,
  "override_buffer_after_minutes": 5,
  "is_available": true,
  "expertise_level": "senior",
  "notes": "Specializes in men's cuts",
  "requires_approval": false
}
```

**Response:** Success message with assignment details

#### DELETE /{staff_id}/services/{service_id} - Remove Service Assignment
Remove a service assignment from a staff member.

**Permissions:** Owner/Admin only

**Response:** 204 No Content

#### GET /{staff_id}/services - Get Staff Services
Retrieve all services assigned to a staff member.

**Query Parameters:**
- `available_only` (boolean, optional): Include only available services (default: true)

**Response:** List of service assignment objects

### 7. Comprehensive Staff View

#### GET /{staff_id}/with-services - Get Staff with Services
Retrieve staff member with all their service assignments and details.

**Permissions:**
- Staff can view their own profile with services
- Front Desk/Admin can view any staff profile with services

**Response:** `StaffWithServices` object

## Data Models

### Staff Roles
- `owner_admin`: Business owner/administrator with full access
- `staff`: Regular staff member with limited access
- `front_desk`: Front desk staff with moderate access

### Time-Off Types
- `personal`: Personal time off
- `vacation`: Vacation time
- `sick`: Sick leave
- `training`: Training or education
- `other`: Other reasons

### Time-Off Status
- `pending`: Awaiting approval
- `approved`: Approved time off
- `denied`: Denied time off
- `cancelled`: Cancelled by staff

### Override Types
- `available`: Override to make time available
- `unavailable`: Override to make time unavailable
- `limited`: Override with limited availability

## Error Handling

The API returns appropriate HTTP status codes:

- `200 OK`: Successful operation
- `201 Created`: Resource created successfully
- `204 No Content`: Operation successful, no content to return
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., overlapping time-off)
- `500 Internal Server Error`: Server error

## Example Usage

### Complete Staff Management Workflow

1. **Create Staff Member**
```bash
POST /api/v1/staff/
{
  "business_id": 1,
  "name": "Jane Doe",
  "email": "jane@salon.com",
  "role": "staff",
  "is_bookable": true
}
```

2. **Set Working Hours**
```bash
POST /api/v1/staff/1/working-hours
[
  {
    "weekday": "monday",
    "start_time": "09:00:00",
    "end_time": "17:00:00"
  }
]
```

3. **Assign Services**
```bash
POST /api/v1/staff/1/services
{
  "service_id": 1,
  "expertise_level": "senior"
}
```

4. **Request Time Off**
```bash
POST /api/v1/staff/1/time-off
{
  "start_datetime": "2024-06-15T09:00:00",
  "end_datetime": "2024-06-17T17:00:00",
  "type": "vacation",
  "reason": "Family vacation"
}
```

5. **Check Availability**
```bash
POST /api/v1/staff/1/availability
{
  "start_datetime": "2024-06-20T00:00:00",
  "end_datetime": "2024-06-21T23:59:59",
  "include_time_offs": true,
  "include_overrides": true
}
```

## Testing

Run the integration tests:

```bash
pytest tests/integration/test_staff_api.py -v
```

## Notes

- All datetime fields use ISO 8601 format
- Business context is enforced for multi-tenant isolation
- Staff can only access their own data unless they have admin privileges
- Soft deletion is used for staff members (sets `is_active = false`)
- Working hours are stored per weekday with optional break times
- Service assignments support per-staff overrides for duration, price, and buffers
