# Receptionist / Records Clerk Rights

## Overview
This document confirms that the Receptionist role has been configured with all required user rights as specified in the requirements.

## Enabled Rights

### UR-1: Register a New Patient
**Status: ✅ ENABLED**

- Permission: `core.add_patient`, `core.change_patient`
- View: `/patients/register/`
- Features:
  - Quick registration with minimal fields (name, sex, and either DOB or age)
  - Supports patients without national ID or fixed address
  - Auto-generates clinic card number (UR-3)
  - Redirects to printable patient card after registration

### UR-2: Search for Existing Patients
**Status: ✅ ENABLED**

- Permission: `core.view_patient`
- View: `/patients/search/`
- Features:
  - Search by name, phone number, or patient card number
  - Tolerant of partial or misspelled input
  - Searches next-of-kin name/phone as fallback
  - Paginated results (20 per page)

### UR-3: Print Patient Card/Number
**Status: ✅ ENABLED**

- Permission: `core.view_patient`
- View: `/patients/<uuid:pk>/card/`
- Features:
  - Printable patient card showing:
    - Clinic-issued card number
    - Patient name, sex, age
    - Contact details
  - Auto-generated on first registration
  - Format: `CL-YYYY-NNNN` (e.g., CL-2026-0001)

### UR-4: See Outstanding Balance
**Status: ✅ ENABLED (NEWLY IMPLEMENTED)**

- Permission: `core.view_invoice`
- Features:
  - **Patient Search Results**: Shows outstanding balance for each patient in search results
  - **Visit History Page**: Displays outstanding balance prominently when viewing patient details
  - Balance shown in red if > 0, otherwise shows "—"
  - Allows receptionist to inform patient before referring to doctor

**Implementation Details:**
- Modified `core/views.py`:
  - `patient_search()`: Annotates each patient with `outstanding_balance` property
  - `patient_visits()`: Calculates and passes `outstanding_balance` to template
- Modified `core/templates/core/patient_search.html`: Added "Outstanding" column
- Modified `core/templates/core/patient_visits.html`: Shows balance in patient header

### UR-5: Work Offline (Internet Outage)
**Status: ✅ ENABLED**

- Feature: Progressive Web App (PWA) with service worker
- Implementation:
  - Service worker caches app shell for offline use
  - Network-first strategy for pages, cache-first for static assets
  - Graceful fallback to cached content when offline
  - All registration and search data stored locally in SQLite
  - Sync module ready for when connection is restored

## Permission Configuration

The receptionist role permissions are defined in `accounts/permissions.py`:

```python
Staff.Role.RECEPTIONIST: [
    (Patient, VIEW_ADD_CHANGE),           # UR-1, UR-2, UR-3
    (Visit, ("view", "add")),             # View visits
    (Invoice, VIEW_ADD_CHANGE),           # UR-4
    (InvoiceLineItem, VIEW_ADD_CHANGE),   # Billing details
    (Payment, VIEW_ADD_CHANGE),           # Record payments
    (Appointment, VIEW_ADD_CHANGE),       # Schedule appointments
    (SMSReminder, VIEW_ADD_CHANGE),       # SMS reminders
],
```

**Note:** Receptionists do NOT have access to:
- Drug stock management (pharmacy functions)
- Staff account management
- Full financial reporting
- Lab test management

This matches the security principle that receptionists handle front-desk operations but not clinical or full financial data.

## Dashboard Menu

When a receptionist logs in, they see the following menu cards:
- ✅ Register patient
- ✅ Search patients
- ✅ Visits
- ✅ Billing
- ✅ Appointments

## Testing

To verify receptionist functionality:

1. Login with receptionist credentials:
   ```
   Username: a.elsie (or your receptionist account)
   Password: (as configured in your system)
   ```

2. Test UR-1: Navigate to "Register patient" and register a new patient

3. Test UR-2: Navigate to "Search patients" and search by name, phone, or card number

4. Test UR-3: After registration, print the patient card

5. Test UR-4: 
   - Create an invoice with outstanding balance for a test patient
   - Search for that patient and verify balance is shown
   - View patient visits and verify balance is displayed

6. Test UR-5: Disconnect internet and verify the app still loads and functions

## Files Modified

1. `core/views.py` - Added outstanding balance calculation to:
   - `patient_search()` view
   - `patient_visits()` view

2. `core/templates/core/patient_search.html` - Added "Outstanding" column

3. `core/templates/core/patient_visits.html` - Added balance display in header

4. `RECEPTIONIST_RIGHTS.md` - This documentation file

## Notes

- All changes are backward compatible
- No database migrations required
- Permissions are automatically synced via `sync_role_groups` command
- The system runs `sync_role_groups` automatically after each `migrate` command
