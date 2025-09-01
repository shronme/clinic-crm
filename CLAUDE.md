# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Barber & Beautician CRM + Booking platform - a lightweight, multi-tenant CRM and online booking system for small barber shops and beauty salons. The project is currently in early development/planning stages.

### Key Features (Planned)

- Multi-business, multi-location support
- Staff and service management with per-staff service mapping
- Real-time appointment scheduling with conflict prevention
- Customer profiles and appointment history
- Post-appointment notes with photos and chemical formulas
- Automated notifications via email/SMS
- Admin web app and customer booking portal (PWA)

### Primary Users

- **Owner/Manager**: Business setup, staff management, analytics
- **Staff/Stylist/Barber**: Availability management, calendar, client notes
- **Front Desk**: Appointment booking and walk-in management
- **Customer**: Service browsing, staff selection, appointment booking

## Project Status

The repository currently contains only the product specification document (`barber_beautician_crm_spec.md`). No code implementation has begun yet.

## Development Setup

**Note**: Development environment and build commands are not yet established as the project is in specification phase.

When development begins, typical commands for this type of application would likely include:

- Development server startup
- Database migrations
- Test execution
- Linting and formatting

## Architecture Notes

Based on the specification, the planned architecture includes:

- Multi-tenant SaaS architecture
- Real-time scheduling system with conflict prevention
- Notification system supporting email and SMS/WhatsApp
- Customer-facing booking portal (PWA)
- Admin dashboard for business management
- Integration capabilities for calendar export and potential payment processing

## Key Business Logic

- **Service Management**: Different services have varying durations, prices, and buffer times
- **Staff Scheduling**: Complex availability management with working hours, breaks, and time-off
- **Conflict Prevention**: Real-time appointment validation to prevent double-booking
- **Multi-tenancy**: Each business operates independently with their own data and settings
- **Customer Journey**: Self-service booking to reduce administrative overhead by ≥70%

## Development Priorities

When implementation begins, focus areas should include:

1. Multi-tenant data architecture design
2. Real-time scheduling engine with conflict detection
3. Staff availability and service mapping system
4. Customer booking flow optimization
5. Notification system integration

## Development process

1. When a devleopment task is received, break it down to the smallest tasks while still being able to create a test (unit/integration or other) for the new task
2. Start the task by creating tests that test the new functionality. These tests will fail at first because the coding is not complete, but run them to make sure.
3. A task is complete when it's tests are passing

## Development guidelines

1. When creating a new model, add a UUID field to it
2. Wen creating an API endppoint for a model that requires it's ID, the API path must use only the UUID
3. When using enums, don't forget to use ".value" to get their string value
