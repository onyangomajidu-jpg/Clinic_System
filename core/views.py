from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from .forms import (
    AppointmentForm,
    DispenseForm,
    DrugForm,
    InvoiceLineItemForm,
    PatientRegistrationForm,
    PaymentForm,
    PrescriptionForm,
    RestockForm,
    VisitForm,
)
from .models import (
    Appointment,
    Drug,
    Invoice,
    Patient,
    Payment,
    Prescription,
    SMSReminder,
    StockMovement,
    Visit,
)
from .reports import (
    diagnosis_report,
    drug_usage_report,
    patient_volume_report,
    revenue_report,
)
from .services import build_reminder_message, send_sms
from .sync import get_all_unsynced, pull_updates, push_unsynced


def health_check(request):
    """Simple health check endpoint to confirm the app is running."""
    return JsonResponse({"status": "ok", "service": "clinic-system"})


@login_required
def patient_register(request):
    """
    UR-1 / FR-1: register a new patient with minimal mandatory fields.

    On success the patient is saved with an auto-generated clinic card
    number (UR-3) and the staff member is taken straight to the printable
    card view so they can hand the patient their card immediately.
    """
    if request.method == "POST":
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            patient = form.save()
            messages.success(
                request,
                f"Patient registered. Card number: {patient.patient_card_no}",
            )
            return redirect("core:patient_card", pk=patient.pk)
    else:
        form = PatientRegistrationForm()

    return render(request, "core/patient_register.html", {"form": form})


@login_required
@require_GET
def patient_search(request):
    """
    UR-2 / FR-2: search for an existing patient by name, phone number, or
    card number, tolerant of partial or misspelled input.

    The query is matched case-insensitively as a substring against name,
    phone, and card number, and also against the next-of-kin name/phone so
    a patient can be found even when the searcher only remembers a relative.
    Results are paginated to keep the page fast on modest hardware (NFR-2).
    """
    query = request.GET.get("q", "").strip()
    patients = Patient.objects.none()
    if query:
        q = Q(full_name__icontains=query)
        # Phone numbers are often entered with spaces/dashes; strip them so
        # "0772 123456" matches "0772123456" and vice versa.
        digits = "".join(ch for ch in query if ch.isdigit())
        if digits:
            q |= Q(phone_number__icontains=digits) | Q(next_of_kin_phone__icontains=digits)
        q |= Q(patient_card_no__icontains=query)
        q |= Q(next_of_kin_name__icontains=query)
        patients = Patient.objects.filter(q).order_by("full_name")

    paginator = Paginator(patients, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    # UR-4: annotate each patient with their outstanding balance so the
    # receptionist can see at a glance whether to mention payment before
    # referring the patient to the clinician.
    patient_list = list(page_obj.object_list)
    for patient in patient_list:
        patient.outstanding_balance = sum(
            (inv.balance_due for inv in patient.invoices.exclude(payment_status=Invoice.PaymentStatus.PAID)),
            0,
        )

    return render(
        request,
        "core/patient_search.html",
        {"query": query, "page_obj": page_obj, "patients": patient_list},
    )


@login_required
def patient_card(request, pk):
    """
    UR-3 / FR-14: printable patient card for first-time (or returning)
    patients. The card shows the clinic-issued number, name, sex, age,
    blood group, and contact details so it can be printed and handed to
    the patient for future visits.
    """
    patient = get_object_or_404(Patient, pk=pk)
    return render(request, "core/patient_card.html", {"patient": patient})


@login_required
def patient_visits(request, pk):
    """
    UR-6 / FR-3: show a patient's full visit history, newest first.

    This is the "quickly pull up a patient's visit history" screen a
    clinician needs before (or during) a consultation. It lists every visit
    with its date, type, status, complaint, and diagnosis, and links to the
    full detail page for each one.
    """
    patient = get_object_or_404(Patient, pk=pk)
    visits = patient.visits.all()

    # UR-4: show the patient's total outstanding balance so the receptionist
    # can remind them before sending them to the doctor.
    outstanding_balance = sum(
        (inv.balance_due for inv in patient.invoices.exclude(payment_status=Invoice.PaymentStatus.PAID)),
        0,
    )

    return render(
        request,
        "core/patient_visits.html",
        {"patient": patient, "visits": visits, "outstanding_balance": outstanding_balance},
    )


@login_required
def visit_create(request, pk):
    """
    UR-7 / FR-3: record a new visit for a patient.

    The attending staff member is captured automatically from the logged-in
    user's Staff profile so the clinician doesn't have to pick themselves
    from a dropdown (UR-10: fast, uncluttered workflow on a shared device).
    Vitals are entered as individual fields and folded into the Visit.vitals
    JSON blob by VisitForm.save().
    """
    patient = get_object_or_404(Patient, pk=pk)
    staff = getattr(request.user, "staff_profile", None)

    if request.method == "POST":
        form = VisitForm(request.POST)
        if form.is_valid():
            visit = form.save(commit=False)
            visit.patient = patient
            if staff is not None:
                visit.attending_staff = staff
            visit.save()
            messages.success(request, "Visit recorded.")
            return redirect("core:visit_detail", pk=visit.pk)
    else:
        form = VisitForm()

    return render(
        request,
        "core/visit_create.html",
        {"form": form, "patient": patient},
    )


@login_required
def visit_detail(request, pk):
    """
    UR-6: full detail of a single visit, including vitals, complaint,
    diagnosis, notes, and status. This is the record a clinician reviews
    when a patient returns for a follow-up.
    """
    visit = get_object_or_404(Visit, pk=pk)
    return render(request, "core/visit_detail.html", {"visit": visit})


# ---------------------------------------------------------------------------
# Pharmacy & Inventory (Day 8)
# UR-8/UR-11/UR-12/UR-13/UR-14, FR-4/FR-5/FR-6
# ---------------------------------------------------------------------------


@login_required
def visit_prescription_create(request, pk):
    """
    UR-8 / FR-4: clinician adds a prescription to a visit, linked to
    pharmacy stock.

    The drug picker (PrescriptionForm) only lists drugs with stock > 0 and
    shows the available quantity next to each name, so the clinician cannot
    unknowingly prescribe an out-of-stock medication.
    """
    visit = get_object_or_404(Visit, pk=pk)
    if request.method == "POST":
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            prescription = form.save(commit=False)
            prescription.visit = visit
            prescription.save()
            messages.success(
                request,
                f"Prescription added: {prescription.drug.name} "
                f"({prescription.quantity_prescribed} {prescription.drug.unit}(s)).",
            )
            return redirect("core:visit_detail", pk=visit.pk)
    else:
        form = PrescriptionForm()

    return render(
        request,
        "core/prescription_form.html",
        {"form": form, "visit": visit},
    )


@login_required
def pharmacy_dashboard(request):
    """
    UR-11/UR-13/FR-6: pharmacy landing page.

    Shows:
    - prescriptions waiting to be dispensed (the day's queue),
    - low-stock drugs (UR-13),
    - near-expiry / expired drugs (UR-13),
    - today's dispensing activity.
    """
    staff = getattr(request.user, "staff_profile", None)

    pending_prescriptions = (
        Prescription.objects.exclude(quantity_prescribed__lte=models.F("quantity_dispensed"))
        .select_related("visit", "visit__patient", "drug")
        .order_by("created_at")[:20]
    )
    dispensed_count = Prescription.objects.filter(
        quantity_dispensed__gt=0
    ).count()

    low_stock = Drug.objects.filter(stock_quantity__lte=models.F("reorder_level")).order_by("stock_quantity")
    near_expiry = Drug.objects.filter(expiry_date__isnull=False).exclude(
        expiry_date__gt=date.today() + timedelta(days=90)
    ).order_by("expiry_date")
    expired = Drug.objects.filter(expiry_date__lt=date.today()).order_by("expiry_date")

    recent_movements = StockMovement.objects.select_related("drug", "staff", "prescription").order_by("-created_at")[:10]

    context = {
        "staff": staff,
        "pending_prescriptions": pending_prescriptions,
        "dispensed_count": dispensed_count,
        "low_stock_drugs": low_stock,
        "near_expiry_drugs": near_expiry,
        "expired_drugs": expired,
        "recent_movements": recent_movements,
        "low_stock_count": low_stock.count(),
        "near_expiry_count": near_expiry.count(),
        "expired_count": expired.count(),
    }
    return render(request, "core/pharmacy_dashboard.html", context)


@login_required
def pharmacy_dispense(request, pk):
    """
    UR-11 / UR-12 / UR-14: pharmacist dispenses against a prescription.

    The quantity defaults to the remaining balance on the prescription, but
    can be reduced for partial dispensing (UR-14). Stock is decremented
    atomically via Drug.dispense() (FR-5), and the dispensed_by staff member
    is captured from the logged-in user for the audit trail (SDD section 8).
    """
    prescription = get_object_or_404(Prescription, pk=pk)
    staff = getattr(request.user, "staff_profile", None)

    if prescription.remaining_quantity <= 0:
        messages.info(request, "This prescription has already been fully dispensed.")
        return redirect("core:pharmacy_dashboard")

    if request.method == "POST":
        form = DispenseForm(request.POST, prescription=prescription)
        if form.is_valid():
            quantity = form.cleaned_data["quantity_to_dispense"]
            try:
                prescription.drug.dispense(
                    quantity=quantity,
                    staff=staff,
                    prescription=prescription,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                return render(
                    request,
                    "core/pharmacy_dispense.html",
                    {"form": form, "prescription": prescription, "staff": staff},
                )
            prescription.quantity_dispensed += quantity
            prescription.dispensed_by = staff
            prescription.save()
            messages.success(
                request,
                f"Dispensed {quantity} {prescription.drug.unit}(s) of "
                f"{prescription.drug.name}.",
            )
            return redirect("core:pharmacy_dashboard")
    else:
        form = DispenseForm(prescription=prescription)

    return render(
        request,
        "core/pharmacy_dispense.html",
        {"form": form, "prescription": prescription, "staff": staff},
    )


@login_required
def pharmacy_drug_list(request):
    """
    UR-13: full drug inventory list with stock levels, alerts, and actions.
    """
    drugs = Drug.objects.order_by("name")
    return render(request, "core/pharmacy_drug_list.html", {"drugs": drugs, "drug_count": drugs.count()})


@login_required
def pharmacy_drug_create(request):
    """
    UR-13: add a new drug to the inventory.
    """
    if request.method == "POST":
        form = DrugForm(request.POST)
        if form.is_valid():
            drug = form.save()
            messages.success(request, f"{drug.name} added to the inventory.")
            return redirect("core:pharmacy_drug_list")
    else:
        form = DrugForm()
    return render(request, "core/pharmacy_drug_form.html", {"form": form, "is_edit": False})


@login_required
def pharmacy_drug_edit(request, pk):
    """
    UR-13: edit a drug (stock level, reorder level, price, expiry).
    """
    drug = get_object_or_404(Drug, pk=pk)
    if request.method == "POST":
        form = DrugForm(request.POST, instance=drug)
        if form.is_valid():
            form.save()
            messages.success(request, f"{drug.name} updated.")
            return redirect("core:pharmacy_drug_list")
    else:
        form = DrugForm(instance=drug)
    return render(
        request,
        "core/pharmacy_drug_form.html",
        {"form": form, "drug": drug, "is_edit": True},
    )


@login_required
def pharmacy_restock(request, pk):
    """
    UR-13: record a stock delivery / restock for a drug.

    The staff member is captured from the logged-in user, and the increase
    is recorded via Drug.restock() which also writes a StockMovement audit
    record.
    """
    drug = get_object_or_404(Drug, pk=pk)
    staff = getattr(request.user, "staff_profile", None)

    if request.method == "POST":
        form = RestockForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data["quantity"]
            notes = form.cleaned_data["notes"]
            drug.restock(quantity=quantity, staff=staff, notes=notes)
            messages.success(
                request,
                f"Restocked {quantity} {drug.unit}(s) of {drug.name}. "
                f"New stock: {drug.stock_quantity} {drug.unit}(s).",
            )
            return redirect("core:pharmacy_drug_list")
    else:
        form = RestockForm()

    return render(
        request,
        "core/pharmacy_restock.html",
        {"form": form, "drug": drug},
    )


@login_required
def pharmacy_stock_movements(request):
    """
    SDD section 8 / FR-11: audit trail of all stock movements.

    Shows who dispensed/restocked what and when, with the resulting balance,
    so administrators can trace any stock change.
    """
    movements = StockMovement.objects.select_related("drug", "staff", "prescription")
    movement_type = request.GET.get("type", "")
    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    paginator = Paginator(movements, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "core/pharmacy_stock_movements.html",
        {
            "page_obj": page_obj,
            "movements": page_obj.object_list,
            "movement_type": movement_type,
        },
    )


# ---------------------------------------------------------------------------
# Billing & Payments (Day 9)
# UR-15/UR-16/UR-17/UR-18, FR-7/FR-8/FR-14
# ---------------------------------------------------------------------------


@login_required
def billing_dashboard(request):
    """
    UR-15/UR-16/UR-18: billing landing page.

    Shows today's collections summary, outstanding balances, and recent
    invoices/payments so the cashier can see the day at a glance.
    """
    staff = getattr(request.user, "staff_profile", None)

    today = date.today()
    today_invoices = Invoice.objects.filter(created_at__date=today)
    today_payments = Payment.objects.filter(created_at__date=today)

    total_collected_today = sum((p.amount for p in today_payments), 0)
    total_billed_today = sum((inv.total_amount for inv in today_invoices), 0)

    outstanding_invoices = (
        Invoice.objects.exclude(payment_status=Invoice.PaymentStatus.PAID)
        .select_related("patient", "visit")
        .order_by("-created_at")[:20]
    )
    outstanding_total = sum(
        (inv.balance_due for inv in Invoice.objects.exclude(payment_status=Invoice.PaymentStatus.PAID)),
        0,
    )

    recent_invoices = Invoice.objects.select_related("patient", "visit").order_by("-created_at")[:10]
    recent_payments = Payment.objects.select_related("invoice", "invoice__patient", "staff").order_by("-created_at")[:10]

    context = {
        "staff": staff,
        "total_collected_today": total_collected_today,
        "total_billed_today": total_billed_today,
        "today_invoice_count": today_invoices.count(),
        "today_payment_count": today_payments.count(),
        "outstanding_invoices": outstanding_invoices,
        "outstanding_total": outstanding_total,
        "outstanding_count": Invoice.objects.exclude(payment_status=Invoice.PaymentStatus.PAID).count(),
        "recent_invoices": recent_invoices,
        "recent_payments": recent_payments,
    }
    return render(request, "core/billing_dashboard.html", context)


@login_required
def billing_invoice_generate(request, pk):
    """
    UR-15 / FR-7: generate an invoice automatically from a visit.

    Uses Invoice.generate_from_visit() to build line items from the
    consultation fee, dispensed drugs, and lab tests. If an invoice already
    exists for the visit, it is returned instead.
    """
    visit = get_object_or_404(Visit, pk=pk)
    staff = getattr(request.user, "staff_profile", None)

    invoice = Invoice.generate_from_visit(visit, staff=staff)
    messages.success(
        request,
        f"Invoice {invoice.invoice_number} generated for {visit.patient.full_name} "
        f"totalling {invoice.total_amount}.",
    )
    return redirect("core:billing_invoice_detail", pk=invoice.pk)


@login_required
def billing_invoice_detail(request, pk):
    """
    UR-15/UR-16/UR-17: full invoice detail with line items, payment history,
    and a form to record a new payment.
    """
    invoice = get_object_or_404(
        Invoice.objects.select_related("patient", "visit", "created_by"),
        pk=pk,
    )
    staff = getattr(request.user, "staff_profile", None)

    if request.method == "POST":
        form = PaymentForm(request.POST, invoice=invoice)
        if form.is_valid():
            amount = form.cleaned_data["amount"]
            method = form.cleaned_data["method"]
            reference = form.cleaned_data["reference"]
            try:
                payment = invoice.record_payment(
                    amount=amount,
                    method=method,
                    staff=staff,
                    reference=reference,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                return render(
                    request,
                    "core/billing_invoice_detail.html",
                    {"invoice": invoice, "form": form, "staff": staff},
                )
            messages.success(
                request,
                f"Payment of {payment.amount} via {payment.get_method_display()} recorded.",
            )
            return redirect("core:billing_invoice_detail", pk=invoice.pk)
    else:
        form = PaymentForm(invoice=invoice)

    return render(
        request,
        "core/billing_invoice_detail.html",
        {"invoice": invoice, "form": form, "staff": staff},
    )


@login_required
def billing_invoice_list(request):
    """
    UR-15: list all invoices, filterable by payment status.
    """
    invoices = Invoice.objects.select_related("patient", "visit").order_by("-created_at")
    status = request.GET.get("status", "")
    if status:
        invoices = invoices.filter(payment_status=status)

    paginator = Paginator(invoices, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "core/billing_invoice_list.html",
        {
            "page_obj": page_obj,
            "invoices": page_obj.object_list,
            "status": status,
        },
    )


@login_required
def billing_invoice_receipt(request, pk):
    """
    UR-17 / FR-14: printable receipt for a paid invoice.

    Shows the invoice number, patient details, line items, payments, and
    balance. Designed to be printed and handed to the patient.
    """
    invoice = get_object_or_404(
        Invoice.objects.select_related("patient", "visit"),
        pk=pk,
    )
    return render(request, "core/billing_invoice_receipt.html", {"invoice": invoice})


@login_required
def billing_daily_summary(request):
    """
    UR-18: daily collections summary.

    Shows total billed, total collected, and payment breakdown by method
    for a selected date (defaults to today).
    """
    staff = getattr(request.user, "staff_profile", None)

    selected_date = request.GET.get("date", "")
    if selected_date:
        try:
            from datetime import datetime

            selected_date = datetime.strptime(selected_date, "%Y-%m-%d").date()
        except ValueError:
            selected_date = date.today()
    else:
        selected_date = date.today()

    day_invoices = Invoice.objects.filter(created_at__date=selected_date)
    day_payments = Payment.objects.filter(created_at__date=selected_date)

    total_billed = sum((inv.total_amount for inv in day_invoices), 0)
    total_collected = sum((p.amount for p in day_payments), 0)

    # Payment breakdown by method
    method_totals = {}
    for method_key, method_label in Invoice.PaymentMethod.choices:
        method_total = sum(
            (p.amount for p in day_payments.filter(method=method_key)), 0
        )
        method_totals[method_label] = method_total

    context = {
        "staff": staff,
        "selected_date": selected_date,
        "total_billed": total_billed,
        "total_collected": total_collected,
        "invoice_count": day_invoices.count(),
        "payment_count": day_payments.count(),
        "method_totals": method_totals,
        "day_invoices": day_invoices.select_related("patient", "visit").order_by("-created_at"),
        "day_payments": day_payments.select_related("invoice", "invoice__patient", "staff").order_by("-created_at"),
    }
    return render(request, "core/billing_daily_summary.html", context)


# ---------------------------------------------------------------------------
# Appointments & SMS Reminders (Day 10)
# UR-24 / FR-10 / SDD 6.6
# ---------------------------------------------------------------------------


@login_required
def appointment_dashboard(request):
    """
    UR-24 / FR-10: appointment scheduling landing page.

    Shows today's appointments, upcoming appointments, and a summary of
    SMS reminders sent.
    """
    staff = getattr(request.user, "staff_profile", None)

    today = timezone.localdate()
    today_appointments = (
        Appointment.objects.filter(appointment_date__date=today)
        .select_related("patient", "visit")
        .order_by("appointment_date")
    )
    upcoming_appointments = (
        Appointment.objects.filter(
            appointment_date__gte=timezone.now(),
            status__in=[Appointment.Status.SCHEDULED, Appointment.Status.REMINDED],
        )
        .select_related("patient", "visit")
        .order_by("appointment_date")[:20]
    )
    recent_reminders = SMSReminder.objects.select_related("appointment", "appointment__patient").order_by("-created_at")[:10]

    context = {
        "staff": staff,
        "today_appointments": today_appointments,
        "upcoming_appointments": upcoming_appointments,
        "recent_reminders": recent_reminders,
        "today_count": today_appointments.count(),
        "upcoming_count": upcoming_appointments.count(),
        "reminder_sent_count": SMSReminder.objects.filter(status="sent").count(),
    }
    return render(request, "core/appointment_dashboard.html", context)


@login_required
def appointment_create(request, pk):
    """
    UR-24 / FR-10: schedule a follow-up appointment for a patient.

    The patient is captured from the URL, and the staff member is captured
    from the logged-in user (UR-10: fast workflow).
    """
    patient = get_object_or_404(Patient, pk=pk)
    staff = getattr(request.user, "staff_profile", None)

    if request.method == "POST":
        form = AppointmentForm(request.POST)
        if form.is_valid():
            appointment = form.save(commit=False)
            appointment.patient = patient
            appointment.scheduled_by = staff
            appointment.save()
            messages.success(
                request,
                f"Appointment scheduled for {patient.full_name} on "
                f"{appointment.appointment_date:%d %b %Y at %H:%M}.",
            )
            return redirect("core:appointment_dashboard")
    else:
        form = AppointmentForm()

    return render(
        request,
        "core/appointment_form.html",
        {"form": form, "patient": patient},
    )


@login_required
def appointment_detail(request, pk):
    """
    UR-24: view a single appointment with its SMS reminder history.
    """
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient", "visit", "scheduled_by"),
        pk=pk,
    )
    return render(
        request,
        "core/appointment_detail.html",
        {"appointment": appointment},
    )


@login_required
def appointment_send_reminder(request, pk):
    """
    UR-24 / FR-10: send an SMS reminder for an appointment.

    Uses the Africa's Talking service (core.services.send_sms). If the
    patient has no phone number, an error message is shown. The SMSReminder
    record is created for the audit trail regardless of success/failure.
    """
    appointment = get_object_or_404(
        Appointment.objects.select_related("patient"),
        pk=pk,
    )

    if not appointment.can_send_reminder:
        messages.error(
            request,
            "This appointment cannot receive an SMS reminder. "
            "The patient needs a registered phone number and an upcoming appointment.",
        )
        return redirect("core:appointment_detail", pk=appointment.pk)

    message = build_reminder_message(appointment)
    result = send_sms(appointment.patient.phone_number, message)

    SMSReminder.objects.create(
        appointment=appointment,
        phone_number=appointment.patient.phone_number,
        message=message,
        status="sent" if result["success"] else "failed",
        provider_message_id=result["message_id"],
        error_message=result["error"],
    )

    if result["success"]:
        appointment.status = Appointment.Status.REMINDED
        appointment.save(update_fields=["status", "last_modified"])
        messages.success(
            request,
            f"SMS reminder sent to {appointment.patient.full_name} "
            f"({appointment.patient.phone_number}).",
        )
    else:
        messages.error(
            request,
            f"SMS reminder failed: {result['error']}",
        )

    return redirect("core:appointment_detail", pk=appointment.pk)


@login_required
def appointment_cancel(request, pk):
    """
    UR-24: cancel a scheduled appointment.
    """
    appointment = get_object_or_404(Appointment, pk=pk)
    appointment.status = Appointment.Status.CANCELLED
    appointment.save(update_fields=["status", "last_modified"])
    messages.success(request, "Appointment cancelled.")
    return redirect("core:appointment_dashboard")


@login_required
def appointment_mark_attended(request, pk):
    """
    UR-24: mark an appointment as attended (patient showed up).
    """
    appointment = get_object_or_404(Appointment, pk=pk)
    appointment.status = Appointment.Status.ATTENDED
    appointment.save(update_fields=["status", "last_modified"])
    messages.success(request, "Appointment marked as attended.")
    return redirect("core:appointment_dashboard")


# ---------------------------------------------------------------------------
# Reporting & Analytics (Day 11)
# UR-19 / UR-23 / FR-11 / SDD Module 7
# ---------------------------------------------------------------------------


def _parse_report_dates(request):
    """Parse start_date/end_date from GET params, defaulting to last 30 days."""
    from datetime import datetime

    start_date = request.GET.get("start_date", "")
    end_date = request.GET.get("end_date", "")
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d").date() if start_date else None
    except ValueError:
        start = None
    try:
        end = datetime.strptime(end_date, "%Y-%m-%d").date() if end_date else None
    except ValueError:
        end = None
    if start is None:
        start = date.today() - timedelta(days=30)
    if end is None:
        end = date.today()
    return start, end


@login_required
def reporting_dashboard(request):
    """
    UR-19 / FR-11: reporting landing page with links to all reports.
    """
    staff = getattr(request.user, "staff_profile", None)
    return render(request, "core/reporting_dashboard.html", {"staff": staff})


@login_required
def report_patient_volumes(request):
    """
    UR-19 / FR-11: patient volumes report over a selectable date range.
    """
    staff = getattr(request.user, "staff_profile", None)
    start_date, end_date = _parse_report_dates(request)
    data = patient_volume_report(start_date, end_date)
    data["staff"] = staff
    return render(request, "core/report_patient_volumes.html", data)


@login_required
def report_diagnoses(request):
    """
    UR-19 / FR-11: common diagnoses report over a selectable date range.
    """
    staff = getattr(request.user, "staff_profile", None)
    start_date, end_date = _parse_report_dates(request)
    diagnoses = diagnosis_report(start_date, end_date)
    return render(
        request,
        "core/report_diagnoses.html",
        {
            "staff": staff,
            "start_date": start_date,
            "end_date": end_date,
            "diagnoses": diagnoses,
        },
    )


@login_required
def report_revenue(request):
    """
    UR-19 / FR-11: revenue report over a selectable date range.
    """
    staff = getattr(request.user, "staff_profile", None)
    start_date, end_date = _parse_report_dates(request)
    data = revenue_report(start_date, end_date)
    data["staff"] = staff
    return render(request, "core/report_revenue.html", data)


@login_required
def report_drug_usage(request):
    """
    UR-19 / FR-11: drug usage report over a selectable date range.
    """
    staff = getattr(request.user, "staff_profile", None)
    start_date, end_date = _parse_report_dates(request)
    drugs = drug_usage_report(start_date, end_date)
    return render(
        request,
        "core/report_drug_usage.html",
        {
            "staff": staff,
            "start_date": start_date,
            "end_date": end_date,
            "drugs": drugs,
        },
    )


@login_required
def report_export_csv(request, report_type):
    """
    UR-23 / FR-11: export a report as CSV for district health reporting
    (DHIS2-friendly format).
    """
    import csv

    from django.http import HttpResponse

    start_date, end_date = _parse_report_dates(request)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = (
        f'attachment; filename="{report_type}_{start_date}_{end_date}.csv"'
    )
    writer = csv.writer(response)

    if report_type == "patient_volumes":
        writer.writerow(["Date", "Visits"])
        for row in patient_volume_report(start_date, end_date)["by_day"]:
            writer.writerow([row["date"], row["visits"]])
    elif report_type == "diagnoses":
        writer.writerow(["Diagnosis", "Count"])
        for row in diagnosis_report(start_date, end_date):
            writer.writerow([row["diagnosis"], row["count"]])
    elif report_type == "revenue":
        writer.writerow(["Date", "Billed", "Collected"])
        for row in revenue_report(start_date, end_date)["by_day"]:
            writer.writerow([row["date"], row["billed"], row["collected"]])
    elif report_type == "drug_usage":
        writer.writerow(["Drug", "Quantity Dispensed", "Prescriptions", "Revenue"])
        for row in drug_usage_report(start_date, end_date):
            writer.writerow(
                [row["drug"], row["quantity_dispensed"], row["prescriptions"], row["revenue"]]
            )
    else:
        return HttpResponse("Unknown report type", status=400)

    return response


# ---------------------------------------------------------------------------
# Offline Capability & Sync (Day 12)
# FR-12 / FR-13 / SDD 4.3
# ---------------------------------------------------------------------------


@login_required
def sync_status(request):
    """
    FR-13: show sync status - how many records are pending sync per model.
    """
    staff = getattr(request.user, "staff_profile", None)
    unsynced = get_all_unsynced(limit_per_model=1000)
    total_pending = sum(len(records) for records in unsynced.values())
    return render(
        request,
        "core/sync_status.html",
        {
            "staff": staff,
            "unsynced": unsynced,
            "total_pending": total_pending,
        },
    )


@login_required
def sync_run(request):
    """
    FR-13: trigger a sync cycle manually (push unsynced records).
    """
    from .sync import sync_all

    result = sync_all()
    return JsonResponse(result)


@login_required
def sync_api_push(request):
    """
    FR-13: API endpoint for the central server to pull unsynced records.
    """
    if request.method != "GET":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    unsynced = get_all_unsynced()
    return JsonResponse({"records": unsynced})


@login_required
def sync_api_pull(request):
    """
    FR-13: API endpoint for the central server to push updates to this clinic.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    import json

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    applied = pull_updates(payload)
    return JsonResponse({"applied": applied})


def pwa_manifest(request):
    """
    PWA manifest (FR-12): enables install as a native app on mobile and desktop.
    """
    manifest = {
        "name": "ALPHAMA MEDICAL CLINIC - Clinic System",
        "short_name": "Clinic System",
        "description": "Clinic Management System for Community Health Clinics",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "any",
        "background_color": "#0f6e5c",
        "theme_color": "#0f6e5c",
        "categories": ["medical", "productivity"],
        "icons": [
            {
                "src": "/static/pwa/icon-72.png",
                "sizes": "72x72",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icon-96.png",
                "sizes": "96x96",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icon-128.png",
                "sizes": "128x128",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icon-144.png",
                "sizes": "144x144",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icon-152.png",
                "sizes": "152x152",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": "/static/pwa/icon-384.png",
                "sizes": "384x384",
                "type": "image/png",
                "purpose": "any",
            },
            {
                "src": "/static/pwa/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
        "screenshots": [],
        "shortcuts": [
            {
                "name": "Register Patient",
                "short_name": "Register",
                "description": "Quickly register a new patient",
                "url": "/patients/register/",
                "icons": [
                    {
                        "src": "/static/pwa/icon-96.png",
                        "sizes": "96x96",
                    }
                ],
            },
            {
                "name": "Search Patients",
                "short_name": "Search",
                "description": "Search for existing patients",
                "url": "/patients/search/",
                "icons": [
                    {
                        "src": "/static/pwa/icon-96.png",
                        "sizes": "96x96",
                    }
                ],
            },
        ],
    }
    return JsonResponse(manifest)


def pwa_service_worker(request):
    """
    PWA service worker (FR-12): caches app shell for offline use.
    """
    js = """
const CACHE_NAME = 'clinic-system-v4';
const APP_SHELL = [
  '/',
  '/offline/',
  '/accounts/login/',
  '/patients/register/',
  '/patients/search/',
  '/manifest.json',
];

// Install: cache the app shell.
// IMPORTANT: cache each URL individually. cache.addAll() aborts the WHOLE
// cache if ANY response is not 2xx - e.g. /patients/register/ returns a 302
// login redirect when the user isn't logged in yet, which used to silently
// prevent anything from being cached and broke offline mode.
self.addEventListener('install', (event) => {
  console.log('[SW] Install');
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      console.log('[SW] Caching app shell');
      await Promise.all(APP_SHELL.map(async (url) => {
        try {
          // Wrap raw urls in Requests so they'll be treated as navigations
          // and sent with credentials (cookies) where relevant.
          const request = new Request(url, { credentials: 'same-origin' });
          const response = await fetch(request);
          if (response.ok && response.type === 'basic') {
            await cache.put(request, response);
          } else {
            console.warn('[SW] Skipping (non-2xx/redirect):', url, response.status);
          }
        } catch (err) {
          console.warn('[SW] Could not cache:', url, err);
        }
      }));
    })()
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  console.log('[SW] Activate');
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => {
          console.log('[SW] Deleting old cache:', key);
          return caches.delete(key);
        })
      );
    })
  );
  self.clients.claim();
});

// Fetch: network-first for HTML pages, cache-first for static assets
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Skip non-GET requests
  if (event.request.method !== 'GET') {
    return;
  }

  // Don't cache API/sync endpoints
  if (url.pathname.includes('/api/') || url.pathname.includes('/sync/')) {
    return;
  }

  // Cache-first for static assets (images, CSS, JS)
  if (url.pathname.startsWith('/static/') || url.pathname.includes('icon')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) {
          return cached;
        }
        return fetch(event.request).then((response) => {
          if (response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          }
          return response;
        }).catch(() => {
          // Return a placeholder for images
          if (url.pathname.includes('icon')) {
            return new Response('', { status: 404 });
          }
        });
      })
    );
    return;
  }

  // Network-first for HTML pages and forms (to ensure fresh data)
  if (event.request.headers.get('accept')?.includes('text/html')) {
    event.respondWith(
      fetch(event.request).then((response) => {
        // Cache successful responses (ignore redirects, e.g. login redirects)
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => {
        // Server is down / offline: serve the cached page if we have it,
        // otherwise show the dedicated offline page for navigations.
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          if (event.request.mode === 'navigate') {
            return caches.match('/offline/');
          }
          return caches.match('/');
        });
      })
    );
    return;
  }

  // Stale-while-revalidate for other requests (API, etc.)
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const fetchPromise = fetch(event.request).then((response) => {
        if (response.status === 200) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      }).catch(() => cached);

      return cached || fetchPromise;
    })
  );
});
"""
    from django.http import HttpResponse

    response = HttpResponse(js, content_type="application/javascript")
    # Never cache the service worker itself, so updates are picked up
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def pwa_offline(request):
    """
    Offline fallback page (FR-12): shown by the service worker when the
    server is unreachable and the requested page is not cached.
    """
    return render(request, "accounts/offline.html")
