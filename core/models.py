import uuid
from datetime import date, timedelta

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
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

    @property
    def days_until_expiry(self):
        """Number of days until expiry (negative if already expired)."""
        if not self.expiry_date:
            return None
        return (self.expiry_date - date.today()).days

    @property
    def is_expired(self):
        """Whether the drug has already passed its expiry date (UR-13)."""
        if not self.expiry_date:
            return False
        return self.expiry_date < date.today()

    @transaction.atomic
    def dispense(self, quantity, staff=None, prescription=None):
        """
        FR-5 / UR-12: atomically decrement stock when a drug is dispensed.

        Validates that enough stock is available, decrements stock_quantity,
        and writes an audit StockMovement record (SDD section 8: audit
        logging for prescription dispensing).

        Raises ValueError if there is not enough stock to fill the order.
        """
        if quantity <= 0:
            raise ValueError("Dispense quantity must be greater than zero.")
        if self.stock_quantity < quantity:
            raise ValueError(
                f"Not enough stock for {self.name}: only {self.stock_quantity} "
                f"{self.unit}(s) available."
            )
        self.stock_quantity -= quantity
        self.save(update_fields=["stock_quantity", "last_modified"])
        StockMovement.objects.create(
            drug=self,
            prescription=prescription,
            movement_type=StockMovement.MovementType.DISPENSE,
            quantity=quantity,
            staff=staff,
            balance_after=self.stock_quantity,
        )
        return self.stock_quantity

    @transaction.atomic
    def restock(self, quantity, staff=None, notes=""):
        """
        Increase stock_quantity and write an audit StockMovement record.

        Used by the pharmacy restock workflow (UR-13: reorder in time).
        """
        if quantity <= 0:
            raise ValueError("Restock quantity must be greater than zero.")
        self.stock_quantity += quantity
        self.save(update_fields=["stock_quantity", "last_modified"])
        StockMovement.objects.create(
            drug=self,
            movement_type=StockMovement.MovementType.RESTOCK,
            quantity=quantity,
            staff=staff,
            notes=notes,
            balance_after=self.stock_quantity,
        )
        return self.stock_quantity


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
    """
    UR-8/UR-11/UR-14: drugs prescribed during a visit, linked to pharmacy stock.

    quantity_prescribed is the amount the clinician ordered;
    quantity_dispensed tracks how much the pharmacist has actually handed
    over so far, so partial dispensing (UR-14) leaves a visible remaining
    balance on the same prescription.
    """

    visit = models.ForeignKey(Visit, on_delete=models.CASCADE, related_name="prescriptions")
    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="prescriptions")
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField()
    quantity_prescribed = models.PositiveIntegerField(
        default=0,
        help_text="Total quantity the clinician prescribed for this course.",
    )
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

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["quantity_dispensed"]),
        ]

    def __str__(self):
        return f"{self.drug.name} for {self.visit.patient.full_name}"

    @property
    def remaining_quantity(self):
        """
        How much of the prescribed course is still to be dispensed (UR-14).
        """
        if self.quantity_prescribed:
            return max(0, self.quantity_prescribed - self.quantity_dispensed)
        return 0

    @property
    def is_fully_dispensed(self):
        return self.remaining_quantity == 0


class StockMovement(SyncedModel):
    """
    Audit trail for every stock change (dispense, restock, adjustment).

    SDD section 8 ("Audit logging") requires prescription dispensing to be
    logged with timestamp and staff ID; this model covers that plus stock
    restocks, so clinic administrators can see exactly how stock levels
    changed over time (FR-11: drug usage trends).
    """

    class MovementType(models.TextChoices):
        DISPENSE = "dispense", "Dispense"
        RESTOCK = "restock", "Restock"
        ADJUSTMENT = "adjustment", "Adjustment"

    drug = models.ForeignKey(Drug, on_delete=models.PROTECT, related_name="stock_movements")
    prescription = models.ForeignKey(
        Prescription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        help_text="Populated when this movement was a dispensing event.",
    )
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.PositiveIntegerField(help_text="Absolute quantity moved.")
    staff = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
        help_text="Staff member who performed the movement (audit trail).",
    )
    notes = models.CharField(max_length=200, blank=True)
    balance_after = models.PositiveIntegerField(
        help_text="Stock level of the drug immediately after this movement."
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_movement_type_display()} {self.quantity} {self.drug.unit}(s) of {self.drug.name}"


class Invoice(SyncedModel):
    """
    UR-15/UR-16/UR-17: one invoice per visit, covering consultation + drugs
    + lab tests, with payment tracking and printable receipts.

    total_amount is the full bill; amount_paid is the running total of all
    Payment records against this invoice. balance_due = total - paid.
    """

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        MOBILE_MONEY = "mobile_money", "Mobile Money"
        INSURANCE = "insurance", "Insurance"

    class PaymentStatus(models.TextChoices):
        PAID = "paid", "Paid"
        PARTIAL = "partial", "Partial"
        UNPAID = "unpaid", "Unpaid"

    invoice_number = models.CharField(
        max_length=30,
        unique=True,
        null=True,
        blank=True,
        help_text="Human-readable invoice number, e.g. INV-2026-0001 (UR-17).",
    )
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
    created_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_invoices",
        help_text="Staff member who generated the invoice (audit trail, SDD §8).",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["invoice_number"]),
            models.Index(fields=["payment_status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_number or '—'} for {self.patient.full_name} - {self.total_amount}"

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def is_fully_paid(self):
        return self.balance_due <= 0

    @transaction.atomic
    def record_payment(self, amount, method, staff=None, reference=""):
        """
        UR-16 / FR-8: record a payment against this invoice.

        Creates a Payment record, updates amount_paid, and recalculates
        payment_status (paid / partial / unpaid). The staff member is
        captured for the audit trail (SDD §8).

        Raises ValueError if the amount is not positive or exceeds the
        outstanding balance.
        """
        if amount <= 0:
            raise ValueError("Payment amount must be greater than zero.")
        if amount > self.balance_due:
            raise ValueError(
                f"Payment of {amount} exceeds the outstanding balance of {self.balance_due}."
            )

        payment = Payment.objects.create(
            invoice=self,
            amount=amount,
            method=method,
            staff=staff,
            reference=reference,
        )

        self.amount_paid += amount
        if self.balance_due <= 0:
            self.payment_status = self.PaymentStatus.PAID
        else:
            self.payment_status = self.PaymentStatus.PARTIAL
        self.payment_method = method
        self.save(update_fields=["amount_paid", "payment_status", "payment_method", "last_modified"])
        return payment

    @classmethod
    @transaction.atomic
    def generate_from_visit(cls, visit, staff=None):
        """
        UR-15 / FR-7: generate an invoice automatically from a visit.

        Builds line items from:
        - a consultation fee (fixed, configurable via settings),
        - any dispensed prescriptions (drug unit_price x quantity_dispensed),
        - any lab tests (a flat fee per test).

        Returns the created Invoice. If an invoice already exists for the
        visit, returns the existing one.
        """
        existing = Invoice.objects.filter(visit=visit).first()
        if existing:
            return existing

        from django.conf import settings

        consultation_fee = getattr(settings, "CONSULTATION_FEE", 5000)

        invoice = Invoice.objects.create(
            visit=visit,
            patient=visit.patient,
            total_amount=0,
            created_by=staff,
        )

        # Consultation fee line item
        InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Consultation fee",
            quantity=1,
            unit_price=consultation_fee,
        )

        # Dispensed drugs line items
        for rx in visit.prescriptions.filter(quantity_dispensed__gt=0):
            if rx.quantity_dispensed > 0:
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    description=f"{rx.drug.name} ({rx.dosage})",
                    quantity=rx.quantity_dispensed,
                    unit_price=rx.drug.unit_price,
                )

        # Lab tests line items
        lab_fee = getattr(settings, "LAB_TEST_FEE", 3000)
        for lab in visit.lab_tests.all():
            InvoiceLineItem.objects.create(
                invoice=invoice,
                description=f"Lab test: {lab.test_name}",
                quantity=1,
                unit_price=lab_fee,
            )

        # Recalculate total from line items
        total = sum(
            (item.quantity * item.unit_price for item in invoice.line_items.all()),
            0,
        )
        invoice.total_amount = total
        invoice.invoice_number = cls._next_invoice_number()
        invoice.save(update_fields=["total_amount", "invoice_number", "last_modified"])
        return invoice

    @staticmethod
    def _next_invoice_number():
        """
        Generate the next invoice number, e.g. INV-2026-0001.
        """
        from datetime import date

        year = date.today().year
        base = Invoice.objects.filter(created_at__year=year).count() + 1
        while True:
            candidate = f"INV-{year}-{base:04d}"
            if not Invoice.objects.filter(invoice_number=candidate).exists():
                return candidate
            base += 1


class Payment(SyncedModel):
    """
    UR-16 / FR-8: individual payment transaction against an invoice.

    A single invoice can have many payments (e.g. partial cash payment
    today, mobile money balance tomorrow). This model provides the audit
    trail and supports partial payments and outstanding balance tracking.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="payments")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    method = models.CharField(max_length=20, choices=Invoice.PaymentMethod.choices)
    staff = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recorded_payments",
        help_text="Staff member who recorded the payment (audit trail, SDD §8).",
    )
    reference = models.CharField(
        max_length=100,
        blank=True,
        help_text="e.g. MTN transaction ID, receipt number, or note.",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.amount} via {self.get_method_display()} on {self.invoice}"


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


class Appointment(SyncedModel):
    """
    UR-24 / FR-10 / SDD 6.6: schedule follow-up appointments and send SMS
    reminders to patients via Africa's Talking gateway.

    Supports the appointment lifecycle: scheduled -> reminded -> attended
    or cancelled. The patient must have a phone number registered to
    receive an SMS reminder (UR-24).
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        REMINDED = "reminded", "Reminded"
        ATTENDED = "attended", "Attended"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No Show"

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="appointments"
    )
    visit = models.ForeignKey(
        Visit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
        help_text="The visit this follow-up appointment was scheduled from.",
    )
    appointment_date = models.DateTimeField()
    reason = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. Follow-up for malaria treatment review.",
    )
    notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.SCHEDULED
    )
    scheduled_by = models.ForeignKey(
        Staff,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scheduled_appointments",
        help_text="Staff member who created the appointment.",
    )

    class Meta:
        ordering = ["appointment_date"]
        indexes = [
            models.Index(fields=["appointment_date"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.patient.full_name} - {self.appointment_date:%Y-%m-%d %H:%M}"

    @property
    def is_upcoming(self):
        return self.appointment_date >= timezone.now() and self.status not in (
            self.Status.CANCELLED,
            self.Status.ATTENDED,
            self.Status.NO_SHOW,
        )

    @property
    def can_send_reminder(self):
        """Patient must have a phone number and appointment not cancelled/attended."""
        return (
            bool(self.patient.phone_number)
            and self.status in (self.Status.SCHEDULED, self.Status.REMINDED)
            and self.appointment_date >= timezone.now()
        )


class SMSReminder(SyncedModel):
    """
    UR-24 / FR-10: log of every SMS reminder sent, with the Africa's Talking
    API response for troubleshooting and audit.

    Stores the message content, recipient phone, whether delivery succeeded,
    and the API's message ID when available.
    """

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="sms_reminders",
    )
    phone_number = models.CharField(
        max_length=20, help_text="Recipient phone number (patient's registered number)."
    )
    message = models.TextField()
    status = models.CharField(
        max_length=20,
        default="pending",
        help_text="pending, sent, failed",
    )
    provider_message_id = models.CharField(
        max_length=100, blank=True, help_text="Africa's Talking message ID."
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"SMS to {self.phone_number} for {self.appointment} - {self.status}"
