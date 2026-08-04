from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET

from .forms import PatientRegistrationForm
from .models import Patient


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