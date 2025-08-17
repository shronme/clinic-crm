# Barber & Beautician CRM + Booking — Product Spec (v1)

Last updated: 17 Aug 2025  
Owner: Product

---
## 1) Summary
A lightweight, multi-tenant CRM and online booking platform for small barber shops and beauty salons. It lets customers self-book appointments with a specific staff member for specific services, while owners get a calendar, CRM, reminders, and post‑appointment notes (including formulas/photos) to improve retention and rebooking.

**Primary outcomes**
- Reduce inbound scheduling overhead by ≥70% via self-serve booking
- Increase rebooking rate by ≥15% via reminders and post‑visit flows
- Raise staff utilization to 70–85% during open hours

**Primary users**
- **Owner/Manager** — sets up business, services, prices, policies; manages staff & capacity; reviews analytics
- **Staff/Stylist/Barber** — manages availability; sees calendar; adds notes/photos; rebooks clients
- **Front Desk** (optional) — books and moves appointments; handles walk‑ins
- **Customer** — browses services, selects staff, books & manages appointments

---
## 2) Scope & Goals
### 2.1 In‑Scope (v1)
- Multi‑business, multi‑location ready (single location per business in v1; multi‑location as v1.1)
- Services & add‑ons (duration, price, buffer — **different per service**)
- Staff profiles & per‑staff service mapping
- Working hours, breaks, time‑off, and override availability
- Real‑time, conflict‑free appointment scheduling
- Customer profiles & history
- Post‑appointment notes (text, structured fields, photos, color/chemical formulas)
- Automated notifications (confirmations, reminders, follow‑ups) via email + SMS/WhatsApp provider
- Simple reporting (appointments, revenue logged, utilization, rebooking rate)
- Admin web app (desktop) + customer booking portal (PWA/embeddable widget)

### 2.2 Out‑of‑Scope (v1) / Later
- Full POS/inventory, product sales (v2)
- Packages/memberships/loyalty (v1.2–v2)
- Multi‑location routing & resource sharing (v1.1+)
- Advanced marketing automation (v2)
- Deep 2‑way calendar sync with external calendars (basic export ICS in v1; 2‑way sync v1.1)
- In‑app payments (Stripe etc.) optional in v1.1

---
## 3) User Journeys
### 3.1 Owner Onboarding
1. Create business → verify email/phone
2. Define location, open hours & closure days
3. Create service categories (Hair, Color, Nails, Brows…)
4. Add services (name, duration, buffer, price, add‑ons)
5. Add staff (photo, bio, roles); map services each staff can perform; set personal calendars (hours, breaks, time‑off)
6. Configure booking policy (lead time, cancellation window, deposit requirement, no‑show policy)
7. Customize notifications & templates
8. Publish booking link / embed widget on website/Instagram/Google Business Profile

**Acceptance criteria**
- Setup can be completed in ≤20 minutes with clear defaults
- Booking link usable immediately after publish; first customer can book end‑to‑end

### 3.2 Customer Booking Flow (self‑serve PWA)
1. Customer opens booking link → sees location, categories, featured services
2. Pick **service(s)** (or choose staff first); see price, duration, add‑ons
3. Pick **staff** (or “Any available”); see next available time slots
4. Select slot → enter name, phone, email; optional notes & consent checkbox
5. Review summary (service, staff, time, price) → confirm
6. Receive confirmation + calendar file; ability to reschedule/cancel within policy from a link

**Acceptance criteria**
- Slot search returns options in < 1.5s for typical shops (≤10 staff)
- Conflicts are prevented; buffers honored; time‑off respected
- Reschedule/cancel links are secure (tokenized) and policy‑aware

### 3.3 Staff: Day‑of Operations
- View agenda (mobile‑friendly) by **Day/Week/Staff**
- Start service → add in‑service notes/photos if needed
- Complete appointment → add structured notes (e.g., color formula, blades used, preferences); quick rebook or “suggest next visit”

**Acceptance criteria**
- Adding notes & photos takes ≤30s
- Notes are staff‑visible; customer‑visible notes optional toggle

---
## 4) Functional Requirements
### 4.1 Business Setup
- Business profile: name, logo, location, contact, timezone, default currency
- Hours & closures (per business + per staff overrides)
- Booking policy: min/max lead time, cancellation window, late/no‑show rules, deposit requirement (off by default in v1)
- Notifications: editable templates (confirm, reminder, follow‑up, reschedule, cancel)

### 4.2 Services & Pricing
- Hierarchical categories; service attributes: name, description, duration, price, **buffer before/after**, color tag
- Add‑ons (e.g., beard trim, toner): extra duration & price; compatible service constraints
- **Per‑staff overrides** for duration/price (optional in v1.1)

### 4.3 Staff & Roles
- Roles: Owner/Admin, Staff, Front Desk (RBAC)
- Staff profile: photo, bio, skills/services, default work hours, breaks, time‑off
- Per‑staff "bookable" toggles; max daily appointments; gap‑filling rules (v1.1)

### 4.4 Availability & Scheduling Engine
- Inputs: business hours, staff hours, existing appts, time‑off, service duration, buffers, add‑ons, lead time, cancellation rules
- Generates bookable slots per staff/service honoring all constraints
- Prevents conflicts on create/reschedule; locks slot for 2–5 minutes during checkout
- Supports “Any staff” search → picks best fit (earliest or owner’s priority rule)
- Handles DST, overlapping buffers, and closed days

### 4.5 Appointment Lifecycle & Policies
- States: **tentative (held)** → **confirmed** → **completed** → **no‑show** / **cancelled**
- Actions: create (self‑serve or admin), confirm, reschedule, cancel, mark arrived, start, complete, no‑show
- Policy checks: min lead time, cancellation window (e.g., no free cancel < 6h), deposit (future), overbooking prevention
- Audit trail of all changes (who/when)

### 4.6 Calendar
- Views: Day/Week/Month; filter by staff/service; color by service or staff
- Drag‑drop to move/resize (policy‑aware)
- Quick create: pick service+staff+time; customer search or quick‑add
- Export ICS (per staff & business); 2‑way sync (Google/Apple/O365) v1.1

### 4.7 Customers (CRM)
- Contact card: name, phone, email, birthday, tags, source, consents
- Timeline: past & upcoming appointments, notes, photos, forms, no‑show history
- Preferences: favorite staff/services, reminders opt‑in
- Search by name/phone; merge duplicates
- CSV import (simple template)

### 4.8 Notes & Media (Post‑Appointment)
- Free‑text notes + **structured templates** (e.g., Color: brand/shade/developer; Haircut: clipper guards; Skin: treatment steps)
- Before/after photos; secure storage; attach up to N images per visit (e.g., 6)
- Private by default (staff/owner only); “share with customer” toggle
- Version history; immutable timestamp; author attribution

### 4.9 Notifications & Communications
- Channels: Email + SMS/WhatsApp provider (owner chooses channel mix)
- Events: booking confirmation, reminder (configurable T‑24h / T‑3h), reschedule, cancel, follow‑up (T+1d) with rebook CTA
- Smart nudges (v1.1): “It’s been 6 weeks since last cut — book now”
- Templates: variables for {customer_name}, {service}, {staff}, {time}, {policy_link}, {manage_link}

### 4.10 Reporting & Insights
- Dashboard tiles: Today’s appointments, no‑shows, utilization %, next available times
- Reports: appointments by staff/service/date; revenue logged (manual in v1), rebooking rate, no‑show %
- Export CSV

### 4.11 Admin Tools
- Data export (customers, appointments, notes metadata)
- Business branding (colors/logo on booking portal)
- Embed widget generator (iframe/script); QR code for booking link

---
## 5) Customer‑Facing Booking Portal (PWA)
- SEO‑friendly public page: services list, staff bios, pricing
- Flow variants: **Service → Staff → Time** or **Staff → Service → Time** (owner default)
- “Any available staff” option
- Real‑time slotting; show next 3 recommended times
- Account‑less checkout (OTP link optional); consent checkbox
- Manage link in messages for reschedule/cancel (policy‑aware)
- Add to calendar (.ics); Add to Wallet pass (v1.1)
- Localized UI (RTL support; multi‑language)

---
## 6) Roles & Permissions (RBAC)
- **Owner/Admin:** everything; can see all notes & photos
- **Staff:** see own calendar & customers; add/edit notes for own appointments; optional visibility to others’ notes (toggle)
- **Front Desk:** create/edit/reschedule for any staff; read customer profiles; add notes flagged as “admin/front desk” type

---
## 7) Data Model (high‑level)
- **Business**(id, name, logo_url, timezone, currency, policy, branding)
- **Location**(id, business_id, address, map_link, hours)
- **Staff**(id, business_id, name, avatar, role, bio, is_bookable)
- **ServiceCategory**(id, business_id, name, position)
- **Service**(id, business_id, category_id, name, description, duration_min, price, buffer_before_min, buffer_after_min, active)
- **StaffService**(id, staff_id, service_id [, override_duration, override_price])
- **WorkingHours**(id, owner_type={business|staff}, owner_id, weekday, start, end)
- **TimeOff**(id, owner_type, owner_id, start_dt, end_dt, reason)
- **Customer**(id, business_id, name, phone, email, birthday, tags[], consents)
- **Appointment**(id, business_id, location_id, customer_id, staff_id, start_dt, end_dt, status, source={web,admin,walkin}, policy_snapshot, notes_summary)
- **AppointmentItem**(id, appointment_id, service_id, add_on_id, duration_min, price)
- **Note**(id, appointment_id, author_staff_id, type={text,template}, payload_json, is_shared_with_customer, created_at)
- **Photo**(id, appointment_id, file_url, created_at)
- **Notification**(id, appointment_id, channel, template, status, sent_at)
- **AuditLog**(id, actor_id, actor_role, entity, entity_id, action, payload_json, created_at)

---
## 8) Scheduling Engine — Logic Details
**Key principle:** **Each service has its own duration and buffers.** The bookable time for any appointment is the **sum of all selected services + add‑ons + their buffers**, after applying any **per‑staff duration overrides**.

**Inputs**
- Business hours; staff hours; staff time‑off/closures
- Existing appointments (expanded by their buffers)
- **Services:** `duration_min`, `buffer_before_min`, `buffer_after_min`
- **Add‑ons:** `extra_duration_min`, `extra_price`
- **Per‑staff overrides:** `override_duration_min` / `override_price` (optional)
- Policies: lead time, cancellation window, max look‑ahead, slot hold duration

**Duration resolution**
- For service *S* with staff *M*:
  - `base = S.duration_min`
  - `duration = StaffService.override_duration_min ?? base`
  - `buffers = (S.buffer_before_min, S.buffer_after_min)`
- For each add‑on *A*: `duration += A.extra_duration_min`
- **Total span** = ordered sum of all selected services (and add‑ons) **+ buffers**.

**Constraints**
- Staff must be bookable and mapped to **every** selected service
- Candidate slot must be within business **and** staff hours
- No overlap with existing appointments **including buffers**
- Respect time‑off/closures, lead time, and look‑ahead

**Slot generation (simplified)**
1. Build the ordered **service chain** and compute effective duration using overrides.
2. Build availability windows per staff: (business ∩ staff) − time‑off.
3. Subtract existing appointments (with buffers) to get free windows.
4. Tile windows at granularity (5–15 min). A start is valid only if the **entire total span** fits without crossing closures/breaks.
5. For **Any staff**: merge across staff; tie‑break (earliest → least buffer waste → preferred staff weight).

**Multi‑service bookings**
- v1: all selected services are consecutive with the **same** staff member.
- v1.1 (future): allow multi‑staff chains (e.g., Colorist → Stylist) with resource hand‑offs.

**Concurrency & locking**
- Soft‑lock chosen slot for 2–5 minutes during checkout.
- Idempotent `create` via client‑supplied key to prevent double booking.

---
## 9) Policies
- **Cancellation window** (e.g., free cancel ≥ 6h before)
- **Reschedule window**
- **No‑show** marking & optional fee recording (manual v1)
- **Deposits** (hold or prepay) — v1.1 with Stripe; amount rule: fixed or % of service price
- **Late arrival** handling (manual note)

---
## 10) Integrations
- **Messaging**: Twilio SMS / WhatsApp Business provider; email (SendGrid/Postmark)
- **Calendar**: ICS export in v1; Google/Apple/Outlook 2‑way sync v1.1
- **Payments**: Stripe (v1.1) for deposits/full prepay; refunds & disputes handled in Stripe
- **Maps**: links to Apple/Google Maps

---
## 11) Admin Web App (Owner/Staff)
**Navigation**: Dashboard • Calendar • Customers • Services • Staff • Reports • Settings

**Dashboard**
- Today’s schedule, KPIs (utilization, no‑show %), next available times

**Calendar**
- Day/Week/Month; Staff lanes; drag‑drop; keyboard shortcuts; conflict guard

**Customers**
- List & search; customer profile with timeline; “Rebook” quick action

**Services**
- Categories, services, add‑ons; duration/price/buffers; visibility on portal

**Staff**
- Profile, services mapping, hours, time‑off

**Reports**
- Filters by date/staff/service; CSV export

**Settings**
- Business profile, policies, templates, branding, booking link & embed code

---
## 12) Customer App/Portal (PWA)
- Mobile‑first; installable; shareable link & QR
- Browse services (with durations/prices), pick staff, pick time
- OTP optional for faster repeat booking; store preferences client‑side
- Manage appointments (reschedule/cancel) per policy

---
## 13) Security, Privacy & Compliance
- Multi‑tenant data isolation by business_id
- Authentication: email+password for admins; magic link/OTP for customers (no password)
- Authorization via RBAC; least‑privilege for staff/front desk
- PII encryption at rest; TLS in transit; media presigned URLs
- Audit log for all critical actions
- Data retention & export tools (owner‑initiated)
- Consent tracking for messaging; unsubscribe links
- RTL & locale support; configurable tax rates (do not hardcode)

---
## 14) Non‑Functional Requirements
- **Performance**: slot search <1.5s (p50), calendar load <1s after warm cache
- **Availability**: 99.9% monthly target
- **Scalability**: up to 50 staff per business, 10k customers, 5k appts/month
- **Observability**: logs, tracing, error reporting, uptime checks
- **Backups**: daily DB snapshots; 30‑day retention; media in versioned storage

---
## 15) Tech Overview (suggested)
- **Frontend (Admin & Portal)**: React + PWA; SSR for SEO on public pages
- **Mobile (optional later)**: Wrap PWA or React Native
- **Backend**: Node.js/TypeScript (NestJS) or Python (FastAPI); REST + Webhooks; background workers for notifications
- **DB**: PostgreSQL (relational scheduling); Redis for slot caching & locks
- **Storage**: S3‑compatible for photos; CDN for media
- **Infra**: Docker; deploy on managed PaaS; IaC via Terraform
- **Integrations**: Twilio/WhatsApp, SendGrid/Postmark, Stripe (v1.1)
- **Testing**: Unit + integration; scheduling engine property tests; e2e booking flows

---
## 16) APIs (v1): Public (Customer) + Admin

### 16.1 Public (Customer‑facing)
`POST /v1/public/availability/search`  
- **Body:** business_id, (location_id), services[] (service_id, add_on_ids[]), preferred_staff_id | any_staff=true, date_range, granularity
- **Returns:** list of slots `{ staff_id, start, end }`

`POST /v1/public/appointments`  
- Create **tentative** appointment; holds slot.
- **Body:** customer details, services/add‑ons, staff_id (or any_staff), start, policy_ack
- **Returns:** `appointment_id`, `confirmation_token`, `hold_expiration`

`POST /v1/public/appointments/{id}/confirm`  
`POST /v1/public/appointments/{id}/reschedule`  
`POST /v1/public/appointments/{id}/cancel`  
- Policy‑aware; secured with tokenized manage link.

### 16.2 Admin (Owner/Staff portal)
**Auth & RBAC**  
- `POST /v1/auth/login`, `POST /v1/auth/magic-link` (optional) → JWT/OAuth2; roles: owner, admin, staff, frontdesk

**Business & Settings**  
- `GET/PUT /v1/business` — profile, timezone, currency, branding  
- `GET/PUT /v1/policies` — lead time, cancellation window, deposits flag (v1 placeholder), reminders config

**Services & Add‑ons**  
- `GET/POST/PUT/DELETE /v1/services`  
- `GET/POST/PUT/DELETE /v1/addons`  
- `GET/POST/DELETE /v1/staff-services` — map services to staff; set overrides (duration/price)

**Staff & Availability**  
- `GET/POST/PUT/DELETE /v1/staff`  
- `GET/POST/DELETE /v1/staff/{id}/hours`  
- `GET/POST/DELETE /v1/staff/{id}/timeoff`

**Calendar & Appointments**  
- `GET /v1/appointments` — filter by date/staff/status  
- `POST /v1/appointments` — admin create (immediate confirm)  
- `PUT /v1/appointments/{id}` — reschedule/change services/staff  
- `POST /v1/appointments/{id}/status` — arrived, started, completed, no‑show

**Customers (CRM)**  
- `GET/POST/PUT/DELETE /v1/customers`  
- `POST /v1/customers/import` — CSV

**Notes & Media**  
- `GET/POST /v1/appointments/{id}/notes`  
- `POST /v1/media/presign` → upload URL; `POST /v1/appointments/{id}/photos`

**Notifications**  
- `GET/PUT /v1/templates` — message templates  
- `POST /v1/notifications/test` — send test to owner

**Reporting**  
- `GET /v1/reports/appointments`  
- `GET /v1/reports/utilization`  
- `GET /v1/reports/rebooking`  
- `GET /v1/reports/export.csv`

**Webhooks** (v1.1)  
- `appointment.created|confirmed|rescheduled|cancelled|completed|no_show`

---
## 17) Analytics & Metrics
- Core: bookings/day, rebooking rate (T+N days), no‑show %, utilization %
- Per staff: revenue proxy, avg service duration vs planned, retention
- Experiments: reminder timing A/B (v1.1)

---
## 18) Acceptance Tests (happy paths)
1. Customer books “Men’s haircut” with Staff A next Tuesday 10:00; confirmation + reminder sent; staff sees it on calendar
2. Owner moves the appointment to 10:30 via drag‑drop; customer receives reschedule message
3. Staff completes appointment, adds notes + 2 photos, marks “suggest rebook in 4 weeks”; follow‑up sent next day
4. Customer reschedules via link; policy respected; no conflicts

---
## 19) Rollout Plan
- Pilot 3–5 shops (≤10 staff each) for 4 weeks
- Instrument feedback capture in portal & admin
- Iterate on availability accuracy and reminder timing

---
## 20) Roadmap
- **v1 (MVP):** core scheduling, CRM, notes, email/SMS reminders, PWA portal, basic reports, ICS export
- **v1.1:** 2‑way calendar sync, WhatsApp template flows, deposits/prepay (Stripe), staff‑level overrides, smart nudges
- **v1.2:** multi‑location, packages/memberships, resource pools (chairs/rooms), loyalty, wallet passes
- **v2:** POS/inventory, marketing automation, referral tracking, advanced analytics dashboard

---
## 21) Implementation Task List

### Foundation Tasks (1-5)
1. **Initialize project structure** - Set up Node.js/TypeScript backend using NestJS framework, React frontend for admin portal, and PostgreSQL database setup
2. **Set up development environment** - Docker containers for PostgreSQL and Redis, package.json with dependencies, TypeScript configuration, and basic project structure
3. **Design and implement database schema** - Create tables based on data model: Business, Location, Staff, ServiceCategory, Service, StaffService, WorkingHours, TimeOff, Customer, Appointment, AppointmentItem, Note, Photo, Notification, AuditLog
4. **Implement multi-tenant data isolation** - Create middleware and business context provider to ensure data separation by business_id across all operations
5. **Create authentication system** - JWT-based auth for admin users (email/password), magic link/OTP system for customers, role-based access control (Owner/Admin, Staff, Front Desk)

### Core Business Logic Tasks (6-11)
6. **Implement Business entity** - CRUD operations for business profile, timezone handling, currency settings, branding configuration, and policy management
7. **Build Service management system** - Hierarchical categories, service CRUD with duration/price/buffers, add-ons with extra duration/price, per-staff service mapping with optional overrides
8. **Develop Staff management** - Staff profiles with roles, working hours configuration, time-off management, service mappings, and availability override system
9. **Implement core scheduling engine** - Availability calculation considering business hours, staff hours, existing appointments, service durations, buffers, time-off, and lead time policies
10. **Build appointment management system** - CRUD operations, status transitions (tentative→confirmed→completed), policy validation (cancellation windows, lead times), conflict prevention with slot locking
11. **Create Customer (CRM) system** - Customer profiles, contact management, appointment history, preferences, search functionality, and CSV import capability

### Public Interface Tasks (12-13)
12. **Implement public booking API endpoints** - Availability search with multi-service support, appointment creation with slot holding, confirmation/reschedule/cancel with tokenized security
13. **Build customer-facing PWA booking portal** - Service browsing, staff selection, time slot picking, responsive design, SEO-friendly pages, installable PWA with offline capability

### Admin Interface Task (14)
14. **Develop admin web application** - Dashboard with KPIs, calendar views (Day/Week/Month), drag-drop appointment management, customer management interface, service configuration UI

### Advanced Features Tasks (15-19)
15. **Implement notes and media system** - Post-appointment notes with structured templates, photo upload with secure storage, version history, privacy controls with staff/customer sharing options
16. **Build notification system** - Email and SMS integration (SendGrid/Twilio), customizable templates, automated triggers (confirmations, reminders, follow-ups), consent management and unsubscribe handling
17. **Create reporting and analytics** - Appointment reports by staff/service/date, utilization tracking, rebooking rate calculation, no-show percentage, revenue logging, CSV export functionality
18. **Implement calendar integration** - ICS export for individual staff and business calendars, downloadable calendar files for customer appointments
19. **Build admin tools** - Data export functionality, business branding customization, booking widget generator with embed codes, QR code generation for booking links

### Production Readiness Tasks (20-24)
20. **Implement security measures** - Data encryption at rest, TLS configuration, audit logging for all critical actions, PII handling compliance, secure media URLs with presigned access
21. **Add comprehensive testing** - Unit tests for business logic, integration tests for APIs, property-based tests for scheduling engine, end-to-end tests for complete booking flows
22. **Optimize performance** - Implement caching strategies for availability searches, database query optimization, background job processing for notifications, CDN setup for static assets
23. **Set up deployment infrastructure** - Docker containerization, environment configuration, database migrations, health checks, monitoring and logging setup
24. **Create documentation** - API documentation, deployment guides, user manuals for business owners, staff training materials, developer setup instructions

---
## 22) Open Decisions (for product workshop)
- Require customer OTP on first booking or make it optional?
- Default reminder timing(s) by service length?
- Photo storage limits & retention defaults
- No‑show fee workflow timing (manual in v1 or gated to payments release)
- Which messaging channels to ship on day‑1 (email+SMS vs email only)

