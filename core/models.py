import uuid
from datetime import date, timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class SyncedModel(models.Model):
    """
    Abstract base class for all clinic data models.

    Per SDD section 5.4 ("Sync Metadata"), every syncable table needs:
    - a UUID primary key (so records created offline at different clinics
      never collide once synced to a shared central database)
    - last_modified / synced / origin_clinic_id, used by the (future) sync
      module for last-write-wins conflict resolution between the local
      SQLite instance and the central PostgreSQL server.

    created_at is included here too since an audit trail of when a record
    first appeared is useful across every model, not just some.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    synced = models.BooleanField(
        default=False,
        help_text="Whether this record has reached the central server.",
    )
    origin_clinic_id = models.UUIDField(
        null=True,
        blank=True,
        help_text="Identifies the source clinic in multi-clinic deployments.",
    )

    class Meta:
        abstract = True


class Staff(SyncedModel):
    """Clinic staff account. UR-20 / SDD 8: role drives RBAC."""

    class Role(models.TextChoices):
        DOCTOR = "doctor", "Doctor"
        NURSE = "nurse", "Nurse"
        CLINICAL_OFFICER = "clinical_officer", "Clinical Officer"
        PHARMACIST = "pharmacist", "Pharmacist"
        RECEPTIONIST = "receptionist", "Receptionist"
        LAB_TECHNICIAN = "lab_technician", "Lab Technician"
        ADMIN = "admin", "Admin / In-charge"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_profile",
        help_text=(
            "Login account for this staff member. Django's built-in auth "
            "handles password hashing, so no raw password field is stored here."
        ),
    )
    name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices)
    phone = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(
        default=True,
        help_text="Uncheck instead of deleting, to preserve visit/prescription history.",
    )

    class Meta:
        verbose_name_plural = "Staff"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.get_role_display()})"


class Patient(SyncedModel):
    """
    UR-1 / FR-1: registration must work with minimal mandatory fields,
    even for patients without a national ID or fixed address.
    """

    class Sex(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"

    class BloodGroup(models.TextChoices):
        A_POS = "A+", "A+"
        A_NEG = "A-", "A-"
        B_POS = "B+", "B+"
        B_NEG = "B-", "B-"
        AB_POS = "AB+", "AB+"
        AB_NEG = "AB-", "AB-"
        O_POS = "O+", "O+"
        O_NEG = "O-", "O-"

    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    estimated_age = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Used when the patient does not know their exact date of birth.",
    )
    sex = models.CharField(max_length=1, choices=Sex.choices)
    phone_number = models.CharField(
        max_length=20, blank=True, help_text="Used for SMS appointment reminders."
    )
    village = models.CharField(max_length=150, blank=True)
    parish = models.CharField(max_length=150, blank=True)
    district = models.CharField(max_length=150, blank=True)
    next_of_kin_name = models.CharField(max_length=200, blank=True)
    next_of_kin_phone = models.CharField(max_length=20, blank=True)
    patient_card_no = models.CharField(
        max_length=50, unique=True, null=True, blank=True,
        help_text="Clinic-issued card number, printed for the patient on first visit.",
    )
    blood_group = models.CharField(max_length=3, choices=BloodGroup.choices, blank=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["phone_number"]),
            models.Index(fields=["patient_card_no"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.patient_card_no or 'no card'})"

    @property
    def age(self):
        """
        Best-effort age in years, for clinical context (UR-7).

        Prefers a precise calculation from date_of_birth; falls back to the
        receptionist-entered estimated_age when the patient does not know
        their exact birth date (UR-1).
        """
        if self.date_of_birth:
            today = date.today()
            return (
                today.year
                - self.date_of_birth.year
                - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
            )
        return self.estimated_age


class Drug(SyncedModel):
    """UR-8/UR-12/UR-13: pharmacy stock backing prescriptions and alerts."""

    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=30, help_text="e.g. tablet, ml, vial")
    stock_quantity = models.PositiveIntegerField(default=0)
    reorder_level = models.PositiveIntegerField(
        default=10, help_text="Low-stock alert triggers at or below this quantity."
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    expiry_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.reorder_level

    @property
    def is_near_expiry(self):
        if not self.expiry_date:
            return False
        return self.expiry_date <= date.today() + timedelta(days=90)


class Visit(SyncedModel):
    """UR-6/UR-7: the primary clinical workspace for a single patient encounter."""

    class VisitType(models.TextChoices):
        OUTPATIENT = "outpatient", "Outpatient"
        FOLLOW_UP = "follow_up", "Follow-up"
        EMERGENCY = "emergency", "Emergency"
        ANTENATAL = "antenatal", "Antenatal"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"
        REFERRED = "referred", "Referred"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="visits")
    visit_date = models.DateTimeField(default=timezone.now)
    visit_type = models.CharField(
        max_length=20, choices=VisitType.choices, default=VisitType.OUTPATIENT
    )
    attending_staff = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attended_visits",
    )
    chief_complaint = models.TextField(blank=True)
    diagnosis = models.TextField(blank=True)
    vitals = models.JSONField(
        default=dict, blank=True, help_text="e.g. BP, temperature, weight, pulse"
    )
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)

    class Meta:
        ordering = ["-visit_date"]

    def __str__(self):
        return f"{self.patient.full_name} - {self.visit_date:%Y-%m-%d %H:%M}"


class Prescription(SyncedModel):
    """UR-8/UR-11/UR-14: drugs prescribed during a visit, linked to pharmacy stock."""

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="prescriptions")
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="prescriptions")
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField()
    quantity_dispensed = models.PositiveIntegerField(
        default=0, help_text="Supports partial dispensing (UR-14)."
    )
    dispensed_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="dispensed_prescriptions",
    )

    def __str__(self):
        return f"{self.drug.name} for {self.visit.patient.full_name}"


class Invoice(SyncedModel):
    """UR-15/UR-16: one invoice per visit, covering consultation + drugs + lab tests."""

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        INSURANCE = "insurance", "Insurance"

    class PaymentStatus(models.TextChoices):
        PAID = "paid", "Paid"
        PARTIAL = "partial", "Partial"
        UNPAID = "unpaid", "Unpaid"

    visit = models.OneToOneField(Visit, on_delete=models.CASCADE, related_name="invoice")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="invoices")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, blank=True
    )
    payment_status = models.CharField(
        max_length=10, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID
    )

    def __str__(self):
        return f"Invoice for {self.patient.full_name} - {self.total_amount}"

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid


class InvoiceLineItem(SyncedModel):
    """
    Child table backing Invoice.line_items (SDD lists this as "JSON / child
    table" - a child table is used here so line items stay queryable and
    reportable, per FR-11).
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="line_items")
    description = models.CharField(
        max_length=200, help_text="e.g. Consultation fee, Amoxicillin, Malaria test"
    )
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self):
        return f"{self.description} x{self.quantity}"


class LabTest(SyncedModel):
    """Optional lab module (UR-9): a test ordered/recorded against a visit."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="lab_tests")
    test_name = models.CharField(max_length=150)
    result = models.TextField(blank=True)
    result_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)

    def __str__(self):
        return f"{self.test_name} ({self.get_status_display()})"
