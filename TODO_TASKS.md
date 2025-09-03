# TODO Tasks - Clinic CRM

This document lists all the TODO tasks found in the codebase that still need implementation.

## 🔐 Authentication & Authorization System

### High Priority

#### 1. JWT Authentication Implementation
- **File**: `app/api/deps/auth.py:17`
- **Task**: Replace placeholder authentication with proper JWT token verification
- **Current State**: Uses simple header-based approach for development
- **Required**: Implement JWT token validation and staff information extraction



#### 2. Business Owner Permissions
- **File**: `app/api/deps/business.py:108`
- **Task**: Implement business owner permission checks
- **Current State**: Placeholder dependency
- **Required**: Check if current user is owner/admin of the business

#### 3. Business Staff Permissions
- **File**: `app/api/deps/business.py:126`
- **Task**: Implement business staff permission checks
- **Current State**: Placeholder dependency
- **Required**: Check if current user is staff/owner/admin of the business

#### 4. Staff Authentication Context
- **File**: `app/api/v1/endpoints/appointments.py:212`
- **Task**: Extract current staff ID from authentication context
- **Current State**: Staff ID is hardcoded as `None`
- **Required**: Get staff ID from JWT token or session

## 📅 Scheduling & Conflict Detection

### High Priority

#### 5. Async Conflict Checking
- **File**: `app/services/scheduling.py:148`
- **Task**: Implement proper conflict checking with async database queries
- **Current State**: Returns all slots as available for basic functionality
- **Required**: Query database for actual conflicts (appointments, time off, etc.)

#### 6. Appointment Conflict Detection
- **File**: `app/services/scheduling.py:374`
- **Task**: Implement appointment conflict checking
- **Current State**: Always returns `False` (no conflicts)
- **Required**: Query appointment table for overlapping appointments

## 🛠️ Service Features

### Medium Priority

#### 7. Service Addons Implementation
- **File**: `app/services/appointment.py:73`
- **Task**: Handle service addons in appointment creation
- **Current State**: Hardcoded as empty list
- **Required**: 
  - Implement addon selection logic
  - Calculate addon pricing
  - Update appointment duration based on addons
  - Store addon information in appointment

## 📋 Implementation Notes

### Authentication System Dependencies
The authentication system TODOs are interconnected. The recommended implementation order:

1. **JWT Authentication** (`auth.py:17`) - Foundation for all auth
2. **Staff Context** (`appointments.py:212`) - Depends on JWT auth
3. **Business Owner Permissions** (`business.py:108`) - Depends on JWT auth
4. **Business Staff Permissions** (`business.py:126`) - Depends on JWT auth

### Scheduling System Dependencies
The scheduling conflict detection TODOs should be implemented together:

1. **Async Conflict Checking** (`scheduling.py:148`) - Core conflict detection
2. **Appointment Conflict Detection** (`scheduling.py:374`) - Specific appointment conflicts

### Service Addons
The addons implementation requires:
- Database schema for addons (if not already present)
- Addon selection UI/API
- Pricing calculation logic
- Duration calculation logic

## 🎯 Priority Matrix

| Priority | Task | Impact | Effort | Dependencies |
|----------|------|--------|--------|--------------|
| **Critical** | JWT Authentication | High | High | None |
| **Critical** | Async Conflict Checking | High | Medium | None |
| **High** | Appointment Conflicts | High | Low | Async Conflicts |
| **Medium** | Staff Context | Medium | Low | JWT Auth |
| **Medium** | Business Owner Permissions | Medium | Low | JWT Auth |
| **Medium** | Business Staff Permissions | Medium | Low | JWT Auth |
| **Medium** | Service Addons | Medium | High | None |

## 🔄 Status Tracking

- [ ] JWT Authentication Implementation
- [ ] Business Owner Permissions
- [ ] Business Staff Permissions
- [ ] Staff Authentication Context
- [x] Async Conflict Checking ✅ **COMPLETED**
- [x] Appointment Conflict Detection ✅ **COMPLETED**
- [x] Service Addons Implementation ✅ **COMPLETED**

## 📋 Implementation Status Details

### ✅ **COMPLETED TASKS**

#### Async Conflict Checking
- **Status**: Fully implemented
- **Location**: `app/services/scheduling.py:148` (`_check_slot_availability` method)
- **Implementation**: Now uses comprehensive `_validate_scheduling_constraints` method with proper database queries for business hours, staff working hours, and appointment conflicts

#### Appointment Conflict Detection  
- **Status**: Fully implemented
- **Location**: `app/services/scheduling.py:401` (`_has_appointment_conflict` method)
- **Implementation**: Complete database query implementation checking for overlapping appointments with proper status filtering and time overlap logic

#### Service Addons Implementation
- **Status**: Fully implemented
- **Location**: `app/services/appointment.py:74` (now implemented)
- **Implementation**: 
  - Complete addon selection and validation logic
  - Automatic duration and pricing calculation including addons
  - Appointment-addon junction table for relationship storage
  - Updated scheduling engine to handle addon durations
  - Comprehensive test coverage

### ❌ **PENDING TASKS**

#### JWT Authentication Implementation
- **Status**: Still placeholder
- **Location**: `app/api/deps/auth.py:18`
- **Current**: Header-based authentication with TODO comment for JWT implementation

#### Business Owner Permissions
- **Status**: Still placeholder  
- **Location**: `app/api/deps/business.py:109`
- **Current**: Placeholder dependency with TODO for owner permission checks

#### Business Staff Permissions
- **Status**: Still placeholder
- **Location**: `app/api/deps/business.py:127` 
- **Current**: Placeholder dependency with TODO for staff permission checks

#### Staff Authentication Context
- **Status**: Still placeholder
- **Location**: `app/api/v1/endpoints/appointments.py:213`
- **Current**: Hardcoded `staff_id=None` with TODO for auth context extraction

#### Service Addons Implementation
- **Status**: Fully implemented
- **Location**: `app/services/appointment.py:74` (now implemented)
- **Implementation**: Complete addon selection, validation, pricing, duration calculation, and storage with appointment-addon junction table

---

*Last updated: January 2025*
*Total tasks: 7*
*Completed: 3/7 (43%)*
*Pending: 4/7 (57%)*
