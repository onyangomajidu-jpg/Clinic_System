from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from .forms import (
    DispenseForm,
    DrugForm,
    PatientRegistrationForm,
    PrescriptionForm,
    RestockForm,
    VisitForm,
)
from .models import Drug, Patient, Prescription, StockMovement, Visit


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

    return render(
        request,
        "core/patient_search.html",
        {"query": query, "page_obj": page_obj, "patients": page_obj.object_list},
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
    return render(
        request,
        "core/patient_visits.html",
        {"patient": patient, "visits": visits},
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
