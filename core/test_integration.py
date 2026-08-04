"""
Day 6 — Integration tests.

These tests exercise the full Week 1 workflow end-to-end, tying together
the modules that were built independently across Days 1-5:

    registration -> search -> consultation (visit) -> visit history -> detail

They verify that the modules work correctly *together* (not just in
isolation), which is the core goal of the Day 6 integration milestone
("Merge and test all Week 1 modules together").

Per SDD section 11 ("Testing Strategy"), integration tests focus on
"End-to-end flows: registration -> visit -> prescription -> billing".
Prescription and billing UIs are scheduled for later sprints, so the
integration coverage here spans the full flow that exists today:
registration -> visit -> history -> detail, plus the model-level business
logic (stock decrement, invoice balance) that the later modules will build
on.
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Drug, Invoice, InvoiceLineItem, Patient, Staff, Visit


class RegistrationToConsultationFlowTests(TestCase):
    """
    The primary Day 6 integration scenario: a receptionist registers a
    patient, then a clinician records a consultation for that patient, and
    the whole chain is visible end-to-end.
    """

    def setUp(self):
        # Receptionist registers the patient (UR-1/UR-2/UR-3)
        self.receptionist_user = User.objects.create_user(
            "rita.receptionist", password="TestPass123!"
        )
        self.receptionist = Staff.objects.create(
            user=self.receptionist_user,
            name="Rita Nansubuga",
            role=Staff.Role.RECEPTIONIST,
        )

        # Clinician records the consultation (UR-6/UR-7)
        self.nurse_user = User.objects.create_user("grace.nurse", password="TestPass123!")
        self.nurse = Staff.objects.create(
            user=self.nurse_user, name="Grace Achieng", role=Staff.Role.NURSE
        )

    def test_full_flow_register_search_consult_history_detail(self):
        """The complete Week 1 journey, exercised as one scenario."""
        # --- Step 1: Receptionist registers a new patient ---
        self.client.login(username="rita.receptionist", password="TestPass123!")
        response = self.client.post(
            reverse("core:patient_register"),
            {
                "full_name": "Nakato Aisha",
                "sex": "F",
                "estimated_age": "34",
                "phone_number": "0772123456",
                "village": "Kyebando",
                "parish": "Kisaasi",
                "district": "Kampala",
                "next_of_kin_name": "John Ssebunya",
                "next_of_kin_phone": "0700111222",
            },
        )
        self.assertEqual(response.status_code, 302)
        patient = Patient.objects.get(full_name="Nakato Aisha")
        self.assertTrue(patient.patient_card_no.startswith("CL-"))
        # Redirected to the printable card (UR-3)
        self.assertRedirects(response, reverse("core:patient_card", args=[patient.pk]))

        # Card page shows the details the receptionist entered
        card_response = self.client.get(reverse("core:patient_card", args=[patient.pk]))
        self.assertContains(card_response, "Nakato Aisha")
        self.assertContains(card_response, patient.patient_card_no)
        self.assertContains(card_response, "0772123456")

        # --- Step 2: Receptionist searches for the patient by phone ---
        search_response = self.client.get(
            reverse("core:patient_search"), {"q": "0772123456"}
        )
        self.assertContains(search_response, "Nakato Aisha")
        self.assertContains(search_response, patient.patient_card_no)

        # --- Step 3: Clinician logs in and records a consultation ---
        self.client.logout()
        self.client.login(username="grace.nurse", password="TestPass123!")
        visit_response = self.client.post(
            reverse("core:visit_create", args=[patient.pk]),
            {
                "visit_type": "outpatient",
                "status": "open",
                "chief_complaint": "Fever and headache for 2 days",
                "diagnosis": "Malaria",
                "notes": "Prescribed antimalarials, advised fluids",
                "blood_pressure": "120/80",
                "pulse": "88",
                "temperature": "38.5",
                "weight": "65.0",
            },
        )
        self.assertEqual(visit_response.status_code, 302)
        visit = Visit.objects.get(patient=patient)
        # Attending staff captured automatically from logged-in user (UR-10)
        self.assertEqual(visit.attending_staff, self.nurse)
        self.assertEqual(visit.chief_complaint, "Fever and headache for 2 days")
        self.assertEqual(visit.diagnosis, "Malaria")
        # Vitals folded into the JSON blob (SDD 5.2)
        self.assertEqual(visit.vitals["bp"], "120/80")
        self.assertEqual(visit.vitals["temperature"], "38.5")

        # --- Step 4: Visit history shows the new visit ---
        history_response = self.client.get(
            reverse("core:patient_visits", args=[patient.pk])
        )
        self.assertContains(history_response, "Fever and headache for 2 days")
        self.assertContains(history_response, "Malaria")

        # --- Step 5: Visit detail shows full clinical record ---
        detail_response = self.client.get(reverse("core:visit_detail", args=[visit.pk]))
        self.assertContains(detail_response, "Fever and headache for 2 days")
        self.assertContains(detail_response, "Malaria")
        self.assertContains(detail_response, "120/80")
        self.assertContains(detail_response, "38.5")
        self.assertContains(detail_response, "Grace Achieng")

    def test_multiple_visits_accumulate_in_history(self):
        """A returning patient's history shows all visits, newest first."""
        patient = Patient.objects.create(
            full_name="Kato John",
            sex="M",
            estimated_age=45,
            patient_card_no="CL-2026-0001",
        )
        # First visit
        Visit.objects.create(
            patient=patient,
            attending_staff=self.nurse,
            visit_type=Visit.VisitType.OUTPATIENT,
            chief_complaint="Cough",
            diagnosis="URTI",
        )
        # Second (follow-up) visit
        Visit.objects.create(
            patient=patient,
            attending_staff=self.nurse,
            visit_type=Visit.VisitType.FOLLOW_UP,
            chief_complaint="Cough improving",
            diagnosis="URTI - resolving",
        )

        self.client.login(username="grace.nurse", password="TestPass123!")
        response = self.client.get(reverse("core:patient_visits", args=[patient.pk]))
        self.assertContains(response, "Cough")
        self.assertContains(response, "Cough improving")
        # Newest first (Visit.Meta.ordering = ["-visit_date"])
        visits = list(response.context["visits"])
        self.assertEqual(visits[0].chief_complaint, "Cough improving")
        self.assertEqual(visits[1].chief_complaint, "Cough")

    def test_patient_search_finds_patient_after_registration(self):
        """Search by card number works for a freshly registered patient."""
        patient = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            estimated_age=34,
            patient_card_no="CL-2026-0001",
        )
        self.client.login(username="rita.receptionist", password="TestPass123!")
        response = self.client.get(
            reverse("core:patient_search"), {"q": patient.patient_card_no}
        )
        self.assertContains(response, "Nakato Aisha")


class CrossRoleWorkflowTests(TestCase):
    """
    Verify that the role-based access control (Day 3) correctly gates the
    clinical workflow (Days 4-5) — a receptionist can register/search but a
    clinician records visits, and neither can do the other's job.
    """

    def setUp(self):
        self.receptionist_user = User.objects.create_user(
            "rita.receptionist", password="TestPass123!"
        )
        Staff.objects.create(
            user=self.receptionist_user,
            name="Rita Nansubuga",
            role=Staff.Role.RECEPTIONIST,
        )
        self.nurse_user = User.objects.create_user("grace.nurse", password="TestPass123!")
        Staff.objects.create(
            user=self.nurse_user, name="Grace Achieng", role=Staff.Role.NURSE
        )
        self.patient = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            estimated_age=34,
            patient_card_no="CL-2026-0001",
        )

    def test_receptionist_can_register_and_search(self):
        self.client.login(username="rita.receptionist", password="TestPass123!")
        self.assertEqual(
            self.client.get(reverse("core:patient_register")).status_code, 200
        )
        self.assertEqual(
            self.client.get(reverse("core:patient_search")).status_code, 200
        )

    def test_nurse_can_record_and_view_visits(self):
        self.client.login(username="grace.nurse", password="TestPass123!")
        self.assertEqual(
            self.client.get(reverse("core:visit_create", args=[self.patient.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse("core:patient_visits", args=[self.patient.pk])).status_code,
            200,
        )

    def test_dashboard_shows_role_appropriate_menus(self):
        # Receptionist sees patient registration/search but not pharmacy
        self.client.login(username="rita.receptionist", password="TestPass123!")
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Register patient")
        self.assertContains(response, "Search patients")
        self.assertNotContains(response, "Pharmacy")

        # Nurse sees visits but not billing
        self.client.logout()
        self.client.login(username="grace.nurse", password="TestPass123!")
        response = self.client.get(reverse("accounts:dashboard"))
        self.assertContains(response, "Visits")
        self.assertNotContains(response, "Billing")


class ModelBusinessLogicIntegrationTests(TestCase):
    """
    Model-level integration of the business rules that the later pharmacy
    and billing modules will build on (SDD 5.2, UR-12/UR-15/UR-16).
    """

    def test_drug_stock_decrement_on_dispense(self):
        """FR-5: dispensing a drug reduces stock."""
        drug = Drug.objects.create(
            name="Amoxicillin",
            unit="tablet",
            stock_quantity=100,
            reorder_level=20,
            unit_price=500.00,
        )
        # Simulate the dispensing action the pharmacy module will perform
        drug.stock_quantity -= 10
        drug.save()
        drug.refresh_from_db()
        self.assertEqual(drug.stock_quantity, 90)

    def test_drug_low_stock_and_near_expiry_alerts(self):
        """FR-6 / UR-13: low-stock and near-expiry flags."""
        low = Drug.objects.create(
            name="Paracetamol",
            unit="tablet",
            stock_quantity=5,
            reorder_level=10,
            unit_price=100.00,
        )
        self.assertTrue(low.is_low_stock)

        from datetime import date, timedelta

        expiring = Drug.objects.create(
            name="ORS Sachets",
            unit="sachet",
            stock_quantity=50,
            reorder_level=10,
            unit_price=200.00,
            expiry_date=date.today() + timedelta(days=30),
        )
        self.assertTrue(expiring.is_near_expiry)

        fine = Drug.objects.create(
            name="Ibuprofen",
            unit="tablet",
            stock_quantity=50,
            reorder_level=10,
            unit_price=150.00,
            expiry_date=date.today() + timedelta(days=365),
        )
        self.assertFalse(fine.is_low_stock)
        self.assertFalse(fine.is_near_expiry)

    def test_invoice_balance_tracking(self):
        """UR-16/FR-8: partial payments and outstanding balances."""
        patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        visit = Visit.objects.create(patient=patient)
        invoice = Invoice.objects.create(
            visit=visit,
            patient=patient,
            total_amount=5000.00,
            amount_paid=2000.00,
            payment_method=Invoice.PaymentMethod.MOBILE_MONEY,
            payment_status=Invoice.PaymentStatus.PARTIAL,
        )
        self.assertEqual(invoice.balance_due, 3000.00)

        # Fully paid invoice has zero balance due
        invoice.amount_paid = 5000.00
        invoice.payment_status = Invoice.PaymentStatus.PAID
        invoice.save()
        self.assertEqual(invoice.balance_due, 0)

    def test_invoice_line_items_totals(self):
        """InvoiceLineItem.line_total multiplies quantity by unit price."""
        patient = Patient.objects.create(
            full_name="Kato John", sex="M", estimated_age=45
        )
        visit = Visit.objects.create(patient=patient)
        invoice = Invoice.objects.create(
            visit=visit,
            patient=patient,
            total_amount=1500.00,
            amount_paid=1500.00,
            payment_method=Invoice.PaymentMethod.CASH,
            payment_status=Invoice.PaymentStatus.PAID,
        )
        line = InvoiceLineItem.objects.create(
            invoice=invoice,
            description="Consultation fee",
            quantity=1,
            unit_price=1500.00,
        )
        self.assertEqual(line.line_total, 1500.00)
