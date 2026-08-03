"""
Role -> permission mapping for the clinic system (FR-9 / UR-20).

This is the single source of truth for what each Staff.role is allowed to
do. It is intentionally kept as plain Python data (not scattered across
admin.py / views.py) so the whole access-control policy can be read and
reviewed in one place, and so it can be synced into Django's Group/
Permission tables automatically (see accounts.signals.sync_role_groups)
instead of relying on someone clicking checkboxes in /admin/ correctly.

Each entry lists a model and which of Django's four built-in per-model
actions (view/add/change/delete) that role gets on it. Deliberately
conservative by default: a role only gets 'delete' where a mistaken record
genuinely needs to be removable, since visit/prescription/invoice history
should normally be corrected via new records, not deletion (data
integrity, per SDD NFR "Data integrity").

Design notes tying back to the requirements docs:
- Receptionist gets Invoice view/add/change (front-desk billing/cashier
  duties per UR-15/16/17) but not delete, and no access to Drug stock
  levels or Staff accounts -- matches UR-20's example of receptionists
  not seeing full financial/reporting detail; day-to-day invoice creation
  is separate from aggregate financial reporting (a later reporting
  module, gated separately).
- Pharmacist gets Drug add/change (stock, reorder level, pricing) and
  Prescription change (to record dispensing / partial dispensing per
  UR-12/UR-14), but not Visit or diagnosis-level fields.
- Doctor/Nurse/Clinical Officer get full clinical documentation access
  (Patient, Visit, Prescription, LabTest) per UR-6/7/8/9, plus read-only
  Drug visibility so they can see what's in stock before prescribing
  (UR-8/FR-4), but no billing or stock-editing rights.
- Lab Technician is scoped to LabTest plus read-only Patient/Visit context.
- Admin gets full CRUD on every clinical model plus Staff account
  management (UR-20/UR-22). Admin does NOT automatically get Django's
  auth.user/auth.group permissions -- creating raw login accounts and
  granting arbitrary permissions stays with a superuser managed by
  whoever deploys the system, so a compromised/misconfigured clinic Admin
  account can't escalate itself to full system control.
"""

from core.models import (
    Drug,
    Invoice,
    InvoiceLineItem,
    LabTest,
    Patient,
    Prescription,
    Staff,
    Visit,
)

VIEW_ADD_CHANGE = ("view", "add", "change")
VIEW_ADD_CHANGE_DELETE = ("view", "add", "change", "delete")
VIEW_ONLY = ("view",)
VIEW_CHANGE = ("view", "change")

ROLE_PERMISSIONS = {
    Staff.Role.RECEPTIONIST: [
        (Patient, VIEW_ADD_CHANGE),
        (Visit, ("view", "add")),
        (Invoice, VIEW_ADD_CHANGE),
        (InvoiceLineItem, VIEW_ADD_CHANGE),
    ],
    Staff.Role.NURSE: [
        (Patient, VIEW_ADD_CHANGE),
        (Visit, VIEW_ADD_CHANGE),
        (Prescription, ("view", "add")),
        (LabTest, ("view", "add")),
        (Drug, VIEW_ONLY),
    ],
    Staff.Role.CLINICAL_OFFICER: [
        (Patient, VIEW_ADD_CHANGE),
        (Visit, VIEW_ADD_CHANGE),
        (Prescription, VIEW_ADD_CHANGE),
        (LabTest, VIEW_ADD_CHANGE),
        (Drug, VIEW_ONLY),
    ],
    Staff.Role.DOCTOR: [
        (Patient, VIEW_ADD_CHANGE),
        (Visit, VIEW_ADD_CHANGE),
        (Prescription, VIEW_ADD_CHANGE),
        (LabTest, VIEW_ADD_CHANGE),
        (Drug, VIEW_ONLY),
    ],
    Staff.Role.PHARMACIST: [
        (Patient, VIEW_ONLY),
        (Prescription, VIEW_CHANGE),
        (Drug, VIEW_ADD_CHANGE),
    ],
    Staff.Role.LAB_TECHNICIAN: [
        (Patient, VIEW_ONLY),
        (Visit, VIEW_ONLY),
        (LabTest, VIEW_CHANGE),
    ],
    Staff.Role.ADMIN: [
        (Patient, VIEW_ADD_CHANGE_DELETE),
        (Visit, VIEW_ADD_CHANGE_DELETE),
        (Drug, VIEW_ADD_CHANGE_DELETE),
        (Prescription, VIEW_ADD_CHANGE_DELETE),
        (Invoice, VIEW_ADD_CHANGE_DELETE),
        (InvoiceLineItem, VIEW_ADD_CHANGE_DELETE),
        (LabTest, VIEW_ADD_CHANGE_DELETE),
        (Staff, VIEW_ADD_CHANGE_DELETE),
    ],
}
