from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from .forms import PatientRegistrationForm, VisitForm
from .models import Patient, Visit


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