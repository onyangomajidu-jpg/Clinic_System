from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import (
    AppointmentForm,
    DispenseForm,
    PatientRegistrationForm,
    PaymentForm,
    PrescriptionForm,
    VisitForm,
)
from .models import (
    Appointment,
    Drug,
    Invoice,
    InvoiceLineItem,
    Patient,
    Payment,
    Prescription,
    SMSReminder,
    Staff,
    StockMovement,
    Visit,
)
from .services import build_reminder_message, send_sms


class PatientRegistrationTests(TestCase):
    """UR-1 / FR-1: register a new patient with minimal mandatory fields."""

    def setUp(self):
        self.user = User.objects.create_user("receptionist", password="TestPass123!")
        Staff.objects.create(
            user=self.user, name="Rita Nansubuga", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="receptionist", password="TestPass123!")

    def test_register_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:patient_register"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_register_page_loads(self):
        response = self.client.get(reverse("core:patient_register"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Register a new patient")

    def test_register_with_minimal_fields(self):
        """Only name + sex (plus one of DOB/age) are required."""
        response = self.client.post(
            reverse("core:patient_register"),
            {
                "full_name": "Nakato Aisha",
                "sex": "F",
                "estimated_age": "34",
            },
        )
        self.assertEqual(response.status_code, 302)
        patient = Patient.objects.get(full_name="Nakato Aisha")
        self.assertEqual(patient.sex, "F")
        self.assertEqual(patient.estimated_age, 34)
        # A clinic card number is auto-assigned (UR-3).
        self.assertTrue(patient.patient_card_no.startswith("CL-"))

    def test_register_requires_name_or_age(self):
        """Neither DOB nor age supplied -> form error."""
        response = self.client.post(
            reverse("core:patient_register"),
            {"full_name": "No Age", "sex": "M"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "either the date of birth")

    def test_register_assigns_unique_card_numbers(self):
        for i in range(3):
            self.client.post(
                reverse("core:patient_register"),
                {"full_name": f"Patient {i}", "sex": "M", "estimated_age": "20"},
            )
        numbers = list(Patient.objects.values_list("patient_card_no", flat=True))
        self.assertEqual(len(numbers), len(set(numbers)))

    def test_register_redirects_to_card(self):
        response = self.client.post(
            reverse("core:patient_register"),
            {"full_name": "Kato John", "sex": "M", "date_of_birth": "1990-01-01"},
        )
        patient = Patient.objects.get(full_name="Kato John")
        self.assertRedirects(response, reverse("core:patient_card", args=[patient.pk]))


class PatientSearchTests(TestCase):
    """UR-2 / FR-2: search by name, phone, or card number, tolerant of
    partial or misspelled input."""

    def setUp(self):
        self.user = User.objects.create_user("receptionist", password="TestPass123!")
        Staff.objects.create(
            user=self.user, name="Rita Nansubuga", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="receptionist", password="TestPass123!")

        self.aisha = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            phone_number="0772123456",
            patient_card_no="CL-2026-0001",
        )
        self.john = Patient.objects.create(
            full_name="Kato John",
            sex="M",
            phone_number="0700111222",
            patient_card_no="CL-2026-0002",
        )

    def test_search_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:patient_search"))
        self.assertEqual(response.status_code, 302)

    def test_search_by_name_partial(self):
        response = self.client.get(reverse("core:patient_search"), {"q": "nak"})
        self.assertContains(response, "Nakato Aisha")
        self.assertNotContains(response, "Kato John")

    def test_search_by_phone(self):
        response = self.client.get(reverse("core:patient_search"), {"q": "0772123456"})
        self.assertContains(response, "Nakato Aisha")

    def test_search_by_phone_with_spaces(self):
        """Search "0772 123 456" still matches stored "0772123456"."""
        response = self.client.get(reverse("core:patient_search"), {"q": "0772 123 456"})
        self.assertContains(response, "Nakato Aisha")

    def test_search_by_card_number(self):
        response = self.client.get(reverse("core:patient_search"), {"q": "CL-2026-0001"})
        self.assertContains(response, "Nakato Aisha")

    def test_search_with_no_results(self):
        response = self.client.get(reverse("core:patient_search"), {"q": "zzzzz"})
        self.assertContains(response, "No patients found")

    def test_search_empty_query_shows_no_results(self):
        response = self.client.get(reverse("core:patient_search"))
        self.assertContains(response, "Enter a search term")


class PatientCardTests(TestCase):
    """UR-3 / FR-14: printable patient card."""

    def setUp(self):
        self.user = User.objects.create_user("receptionist", password="TestPass123!")
        Staff.objects.create(
            user=self.user, name="Rita Nansubuga", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="receptionist", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            patient_card_no="CL-2026-0001",
            blood_group="O+",
        )

    def test_card_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:patient_card", args=[self.patient.pk]))
        self.assertEqual(response.status_code, 302)

    def test_card_shows_patient_details(self):
        response = self.client.get(reverse("core:patient_card", args=[self.patient.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nakato Aisha")
        self.assertContains(response, "CL-2026-0001")
        self.assertContains(response, "O+")

    def test_card_404_for_unknown_patient(self):
        from uuid import uuid4

        response = self.client.get(reverse("core:patient_card", args=[uuid4()]))
        self.assertEqual(response.status_code, 404)


class PatientRegistrationFormTests(TestCase):
    """Pure form unit tests (no HTTP)."""

    def test_dob_or_age_required(self):
        form = PatientRegistrationForm(data={"full_name": "X", "sex": "M"})
        self.assertFalse(form.is_valid())
        self.assertIn("either the date of birth", form.errors["__all__"][0])

    def test_dob_alone_is_valid(self):
        form = PatientRegistrationForm(
            data={"full_name": "X", "sex": "M", "date_of_birth": "1980-01-01"}
        )
        self.assertTrue(form.is_valid())


class VisitManagementTests(TestCase):
    """UR-6 / UR-7 / FR-3: record and review patient visits."""

    def setUp(self):
        self.user = User.objects.create_user("nurse", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Grace Achieng", role=Staff.Role.NURSE
        )
        self.client.login(username="nurse", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            estimated_age=34,
            patient_card_no="CL-2026-0001",
        )

    def test_patient_visits_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse("core:patient_visits", args=[self.patient.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_patient_visits_empty(self):
        response = self.client.get(
            reverse("core:patient_visits", args=[self.patient.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No visits recorded yet")

    def test_patient_visits_lists_visits(self):
        Visit.objects.create(
            patient=self.patient,
            attending_staff=self.staff,
            visit_type=Visit.VisitType.OUTPATIENT,
            chief_complaint="Fever and headache",
            diagnosis="Malaria",
        )
        response = self.client.get(
            reverse("core:patient_visits", args=[self.patient.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fever and headache")
        self.assertContains(response, "Malaria")

    def test_visit_create_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse("core:visit_create", args=[self.patient.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_visit_create_page_loads(self):
        response = self.client.get(
            reverse("core:visit_create", args=[self.patient.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Record a visit")
        self.assertContains(response, "Nakato Aisha")

    def test_visit_create_saves_visit(self):
        response = self.client.post(
            reverse("core:visit_create", args=[self.patient.pk]),
            {
                "visit_type": "outpatient",
                "status": "open",
                "chief_complaint": "Cough for 3 days",
                "diagnosis": "Upper respiratory tract infection",
                "notes": "Advise fluids and rest",
                "blood_pressure": "120/80",
                "pulse": "72",
                "temperature": "37.0",
                "weight": "65.0",
            },
        )
        self.assertEqual(response.status_code, 302)
        visit = Visit.objects.get(patient=self.patient)
        self.assertEqual(visit.chief_complaint, "Cough for 3 days")
        self.assertEqual(visit.diagnosis, "Upper respiratory tract infection")
        self.assertEqual(visit.attending_staff, self.staff)
        # Vitals folded into the JSON blob (SDD 5.2)
        self.assertEqual(visit.vitals["bp"], "120/80")
        self.assertEqual(visit.vitals["pulse"], "72")
        self.assertEqual(visit.vitals["temperature"], "37.0")
        self.assertEqual(visit.vitals["weight"], "65.0")

    def test_visit_create_redirects_to_detail(self):
        response = self.client.post(
            reverse("core:visit_create", args=[self.patient.pk]),
            {
                "visit_type": "follow_up",
                "status": "open",
                "chief_complaint": "Review",
                "diagnosis": "Hypertension",
            },
        )
        visit = Visit.objects.get(patient=self.patient)
        self.assertRedirects(response, reverse("core:visit_detail", args=[visit.pk]))

    def test_visit_detail_requires_login(self):
        visit = Visit.objects.create(
            patient=self.patient, attending_staff=self.staff
        )
        self.client.logout()
        response = self.client.get(reverse("core:visit_detail", args=[visit.pk]))
        self.assertEqual(response.status_code, 302)

    def test_visit_detail_shows_vitals(self):
        visit = Visit.objects.create(
            patient=self.patient,
            attending_staff=self.staff,
            chief_complaint="Fever",
            diagnosis="Malaria",
            vitals={"bp": "110/70", "pulse": "80", "temperature": "38.5", "weight": "60.0"},
        )
        response = self.client.get(reverse("core:visit_detail", args=[visit.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fever")
        self.assertContains(response, "Malaria")
        self.assertContains(response, "110/70")
        self.assertContains(response, "38.5")

    def test_visit_detail_404_for_unknown(self):
        from uuid import uuid4

        response = self.client.get(reverse("core:visit_detail", args=[uuid4()]))
        self.assertEqual(response.status_code, 404)


class VisitFormTests(TestCase):
    """Pure form unit tests for VisitForm (no HTTP)."""

    def test_minimal_visit_is_valid(self):
        form = VisitForm(
            data={
                "visit_type": "outpatient",
                "status": "open",
                "chief_complaint": "Headache",
                "diagnosis": "Migraine",
            }
        )
        self.assertTrue(form.is_valid())

    def test_vitals_are_optional(self):
        form = VisitForm(
            data={
                "visit_type": "outpatient",
                "status": "open",
                "chief_complaint": "Check-up",
            }
        )
        self.assertTrue(form.is_valid())
        visit = form.save(commit=False)
        self.assertEqual(visit.vitals, {})

    def test_vitals_fold_into_json(self):
        form = VisitForm(
            data={
                "visit_type": "outpatient",
                "status": "open",
                "chief_complaint": "Fever",
                "blood_pressure": "130/85",
                "pulse": "88",
                "temperature": "37.5",
                "weight": "70.0",
            }
        )
        self.assertTrue(form.is_valid())
        visit = form.save(commit=False)
        self.assertEqual(visit.vitals["bp"], "130/85")
        self.assertEqual(visit.vitals["pulse"], "88")
        self.assertEqual(visit.vitals["temperature"], "37.5")
        self.assertEqual(visit.vitals["weight"], "70.0")


class PharmacyDrugModelTests(TestCase):
    """UR-13 / FR-5 / FR-6: Drug stock model behaviour."""

    def setUp(self):
        self.drug = Drug.objects.create(
            name="Amoxicillin",
            unit="tablet",
            stock_quantity=50,
            reorder_level=10,
            unit_price="0.50",
            expiry_date="2027-01-01",
        )

    def test_is_low_stock(self):
        self.assertFalse(self.drug.is_low_stock)
        self.drug.stock_quantity = 10
        self.assertTrue(self.drug.is_low_stock)
        self.drug.stock_quantity = 5
        self.assertTrue(self.drug.is_low_stock)

    def test_is_near_expiry(self):
        from datetime import date, timedelta

        # 60 days out -> near expiry
        self.drug.expiry_date = date.today() + timedelta(days=60)
        self.assertTrue(self.drug.is_near_expiry)
        # 120 days out -> not near expiry
        self.drug.expiry_date = date.today() + timedelta(days=120)
        self.assertFalse(self.drug.is_near_expiry)

    def test_is_expired(self):
        from datetime import date, timedelta

        self.drug.expiry_date = date.today() - timedelta(days=1)
        self.assertTrue(self.drug.is_expired)
        self.drug.expiry_date = date.today() + timedelta(days=1)
        self.assertFalse(self.drug.is_expired)

    def test_dispense_decrements_stock_and_logs_movement(self):
        new_stock = self.drug.dispense(quantity=10)
        self.assertEqual(new_stock, 40)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.stock_quantity, 40)
        movement = StockMovement.objects.get(drug=self.drug)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.DISPENSE)
        self.assertEqual(movement.quantity, 10)
        self.assertEqual(movement.balance_after, 40)
        self.assertIsNone(movement.prescription)

    def test_dispense_raises_when_insufficient_stock(self):
        with self.assertRaises(ValueError):
            self.drug.dispense(quantity=100)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.stock_quantity, 50)
        self.assertEqual(StockMovement.objects.count(), 0)

    def test_dispense_zero_raises(self):
        with self.assertRaises(ValueError):
            self.drug.dispense(quantity=0)

    def test_restock_increases_stock_and_logs_movement(self):
        new_stock = self.drug.restock(quantity=100, staff=None, notes="Supplier delivery")
        self.assertEqual(new_stock, 150)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.stock_quantity, 150)
        movement = StockMovement.objects.get(drug=self.drug)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.RESTOCK)
        self.assertEqual(movement.quantity, 100)
        self.assertEqual(movement.balance_after, 150)
        self.assertEqual(movement.notes, "Supplier delivery")


class PrescriptionModelTests(TestCase):
    """UR-14: partial dispensing and remaining quantity tracking."""

    def setUp(self):
        self.user = User.objects.create_user("pharmacist", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Sarah Nakato", role=Staff.Role.PHARMACIST
        )
        self.patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.drug = Drug.objects.create(
            name="Paracetamol",
            unit="tablet",
            stock_quantity=100,
            reorder_level=20,
            unit_price="0.10",
        )
        self.prescription = Prescription.objects.create(
            visit=self.visit,
            drug=self.drug,
            dosage="500mg",
            frequency="3 times a day",
            duration_days=7,
            quantity_prescribed=21,
        )

    def test_remaining_quantity_initial(self):
        self.assertEqual(self.prescription.remaining_quantity, 21)
        self.assertFalse(self.prescription.is_fully_dispensed)

    def test_remaining_quantity_after_partial_dispense(self):
        # Simulate partial dispensing (UR-14)
        self.drug.dispense(quantity=10, staff=self.staff, prescription=self.prescription)
        self.prescription.quantity_dispensed = 10
        self.prescription.dispensed_by = self.staff
        self.prescription.save()
        self.assertEqual(self.prescription.remaining_quantity, 11)
        self.assertFalse(self.prescription.is_fully_dispensed)

    def test_fully_dispensed(self):
        self.drug.dispense(quantity=21, staff=self.staff, prescription=self.prescription)
        self.prescription.quantity_dispensed = 21
        self.prescription.dispensed_by = self.staff
        self.prescription.save()
        self.assertEqual(self.prescription.remaining_quantity, 0)
        self.assertTrue(self.prescription.is_fully_dispensed)

    def test_dispense_links_stock_movement_to_prescription(self):
        self.drug.dispense(quantity=5, staff=self.staff, prescription=self.prescription)
        movement = StockMovement.objects.get(drug=self.drug, prescription=self.prescription)
        self.assertEqual(movement.staff, self.staff)
        self.assertEqual(movement.movement_type, StockMovement.MovementType.DISPENSE)


class PharmacyDashboardTests(TestCase):
    """UR-11 / UR-13 / FR-6: pharmacy landing page with queue and alerts."""

    def setUp(self):
        self.user = User.objects.create_user("pharmacist", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Sarah Nakato", role=Staff.Role.PHARMACIST
        )
        self.client.login(username="pharmacist", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.drug = Drug.objects.create(
            name="Amoxicillin",
            unit="tablet",
            stock_quantity=5,
            reorder_level=10,
            unit_price="0.50",
        )
        self.prescription = Prescription.objects.create(
            visit=self.visit,
            drug=self.drug,
            dosage="500mg",
            frequency="3 times a day",
            duration_days=7,
            quantity_prescribed=21,
        )

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:pharmacy_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_shows_pending_prescriptions(self):
        response = self.client.get(reverse("core:pharmacy_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amoxicillin")
        self.assertContains(response, "Nakato Aisha")

    def test_dashboard_shows_low_stock_alert(self):
        response = self.client.get(reverse("core:pharmacy_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Low stock alerts")
        self.assertContains(response, "Amoxicillin")

    def test_dashboard_empty_still_loads(self):
        Prescription.objects.all().delete()
        Drug.objects.all().delete()
        response = self.client.get(reverse("core:pharmacy_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No prescriptions waiting")


class PharmacyDispenseViewTests(TestCase):
    """UR-11 / UR-12: pharmacist dispenses against a prescription."""

    def setUp(self):
        self.user = User.objects.create_user("pharmacist", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Sarah Nakato", role=Staff.Role.PHARMACIST
        )
        self.client.login(username="pharmacist", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.drug = Drug.objects.create(
            name="Paracetamol",
            unit="tablet",
            stock_quantity=50,
            reorder_level=10,
            unit_price="0.10",
        )
        self.prescription = Prescription.objects.create(
            visit=self.visit,
            drug=self.drug,
            dosage="500mg",
            frequency="3 times a day",
            duration_days=7,
            quantity_prescribed=21,
        )

    def test_dispense_page_loads(self):
        response = self.client.get(
            reverse("core:pharmacy_dispense", args=[self.prescription.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dispense medication")
        self.assertContains(response, "Paracetamol")

    def test_dispense_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse("core:pharmacy_dispense", args=[self.prescription.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_dispense_full_quantity(self):
        response = self.client.post(
            reverse("core:pharmacy_dispense", args=[self.prescription.pk]),
            {"quantity_to_dispense": "21"},
        )
        self.assertEqual(response.status_code, 302)
        self.prescription.refresh_from_db()
        self.drug.refresh_from_db()
        self.assertEqual(self.prescription.quantity_dispensed, 21)
        self.assertEqual(self.drug.stock_quantity, 29)
        self.assertEqual(self.prescription.dispensed_by, self.staff)
        movement = StockMovement.objects.get(
            drug=self.drug, prescription=self.prescription
        )
        self.assertEqual(movement.quantity, 21)
        self.assertEqual(movement.balance_after, 29)

    def test_partial_dispense(self):
        """UR-14: dispense only part of the prescription."""
        response = self.client.post(
            reverse("core:pharmacy_dispense", args=[self.prescription.pk]),
            {"quantity_to_dispense": "10"},
        )
        self.assertEqual(response.status_code, 302)
        self.prescription.refresh_from_db()
        self.drug.refresh_from_db()
        self.assertEqual(self.prescription.quantity_dispensed, 10)
        self.assertEqual(self.drug.stock_quantity, 40)

    def test_cannot_dispense_more_than_remaining(self):
        response = self.client.post(
            reverse("core:pharmacy_dispense", args=[self.prescription.pk]),
            {"quantity_to_dispense": "22"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cannot dispense more than the remaining")
        self.prescription.refresh_from_db()
        self.assertEqual(self.prescription.quantity_dispensed, 0)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.stock_quantity, 50)

    def test_cannot_dispense_more_than_stock(self):
        self.drug.stock_quantity = 5
        self.drug.save()
        response = self.client.post(
            reverse("core:pharmacy_dispense", args=[self.prescription.pk]),
            {"quantity_to_dispense": "10"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "in stock")

    def test_already_fully_dispensed_redirects(self):
        self.drug.dispense(quantity=21, staff=self.staff, prescription=self.prescription)
        self.prescription.quantity_dispensed = 21
        self.prescription.save()
        response = self.client.get(
            reverse("core:pharmacy_dispense", args=[self.prescription.pk])
        )
        self.assertRedirects(response, reverse("core:pharmacy_dashboard"))


class PrescriptionFormTests(TestCase):
    """UR-8 / FR-4: prescription form linked to pharmacy stock."""

    def setUp(self):
        self.out_of_stock = Drug.objects.create(
            name="Out of Stock Drug",
            unit="tablet",
            stock_quantity=0,
            reorder_level=10,
            unit_price="1.00",
        )
        self.in_stock = Drug.objects.create(
            name="In Stock Drug",
            unit="tablet",
            stock_quantity=100,
            reorder_level=10,
            unit_price="1.00",
        )

    def test_form_only_shows_in_stock_drugs(self):
        form = PrescriptionForm()
        drugs = form.fields["drug"].queryset
        self.assertIn(self.in_stock, drugs)
        self.assertNotIn(self.out_of_stock, drugs)

    def test_form_is_valid_for_in_stock_drug(self):
        form = PrescriptionForm(
            data={
                "drug": self.in_stock.pk,
                "dosage": "500mg",
                "frequency": "3 times a day",
                "duration_days": "7",
                "quantity_prescribed": "21",
            }
        )
        self.assertTrue(form.is_valid())

    def test_quantity_must_be_positive(self):
        form = PrescriptionForm(
            data={
                "drug": self.in_stock.pk,
                "dosage": "500mg",
                "frequency": "3 times a day",
                "duration_days": "7",
                "quantity_prescribed": "0",
            }
        )
        self.assertFalse(form.is_valid())


class DispenseFormTests(TestCase):
    """UR-14: dispense form validation against prescription and stock."""

    def setUp(self):
        self.drug = Drug.objects.create(
            name="Paracetamol",
            unit="tablet",
            stock_quantity=30,
            reorder_level=10,
            unit_price="0.10",
        )
        self.patient = Patient.objects.create(
            full_name="Test Patient", sex="M", estimated_age=25
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.prescription = Prescription.objects.create(
            visit=self.visit,
            drug=self.drug,
            dosage="500mg",
            frequency="3 times a day",
            duration_days=7,
            quantity_prescribed=21,
        )

    def test_remaining_quantity_is_initial(self):
        form = DispenseForm(prescription=self.prescription)
        self.assertEqual(
            form.fields["quantity_to_dispense"].initial,
            21,
        )

    def test_valid_full_dispense(self):
        form = DispenseForm(
            {"quantity_to_dispense": "21"}, prescription=self.prescription
        )
        self.assertTrue(form.is_valid())

    def test_valid_partial_dispense(self):
        form = DispenseForm(
            {"quantity_to_dispense": "5"}, prescription=self.prescription
        )
        self.assertTrue(form.is_valid())

    def test_rejects_more_than_remaining(self):
        form = DispenseForm(
            {"quantity_to_dispense": "22"}, prescription=self.prescription
        )
        self.assertFalse(form.is_valid())

    def test_rejects_more_than_stock(self):
        self.drug.stock_quantity = 5
        self.drug.save()
        form = DispenseForm(
            {"quantity_to_dispense": "10"}, prescription=self.prescription
        )
        self.assertFalse(form.is_valid())


class PharmacyDrugInventoryTests(TestCase):
    """UR-13: manage drug inventory (list, add, edit, restock)."""

    def setUp(self):
        self.user = User.objects.create_user("pharmacist", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Sarah Nakato", role=Staff.Role.PHARMACIST
        )
        self.client.login(username="pharmacist", password="TestPass123!")

        self.drug = Drug.objects.create(
            name="Amoxicillin",
            unit="tablet",
            stock_quantity=20,
            reorder_level=10,
            unit_price="0.50",
            expiry_date="2027-01-01",
        )

    def test_drug_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:pharmacy_drug_list"))
        self.assertEqual(response.status_code, 302)

    def test_drug_list_shows_drugs(self):
        response = self.client.get(reverse("core:pharmacy_drug_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amoxicillin")

    def test_drug_create_page_loads(self):
        response = self.client.get(reverse("core:pharmacy_drug_create"))
        self.assertEqual(response.status_code, 200)

    def test_drug_create_saves_drug(self):
        response = self.client.post(
            reverse("core:pharmacy_drug_create"),
            {
                "name": "Metronidazole",
                "unit": "tablet",
                "stock_quantity": "100",
                "reorder_level": "20",
                "unit_price": "0.20",
                "expiry_date": "2027-06-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Drug.objects.filter(name="Metronidazole").exists())

    def test_drug_edit_page_loads(self):
        response = self.client.get(
            reverse("core:pharmacy_drug_edit", args=[self.drug.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amoxicillin")

    def test_drug_edit_updates_drug(self):
        response = self.client.post(
            reverse("core:pharmacy_drug_edit", args=[self.drug.pk]),
            {
                "name": "Amoxicillin 500mg",
                "unit": "tablet",
                "stock_quantity": "25",
                "reorder_level": "15",
                "unit_price": "0.60",
                "expiry_date": "2027-12-01",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.name, "Amoxicillin 500mg")
        self.assertEqual(self.drug.stock_quantity, 25)
        self.assertEqual(self.drug.reorder_level, 15)

    def test_restock_page_loads(self):
        response = self.client.get(
            reverse("core:pharmacy_restock", args=[self.drug.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Restock Amoxicillin")

    def test_restock_increases_stock_and_logs(self):
        response = self.client.post(
            reverse("core:pharmacy_restock", args=[self.drug.pk]),
            {"quantity": "100", "notes": "Monthly delivery"},
        )
        self.assertEqual(response.status_code, 302)
        self.drug.refresh_from_db()
        self.assertEqual(self.drug.stock_quantity, 120)
        movement = StockMovement.objects.get(
            drug=self.drug, movement_type=StockMovement.MovementType.RESTOCK
        )
        self.assertEqual(movement.quantity, 100)
        self.assertEqual(movement.balance_after, 120)
        self.assertEqual(movement.staff, self.staff)
        self.assertEqual(movement.notes, "Monthly delivery")


class PharmacyStockMovementsTests(TestCase):
    """SDD section 8: audit trail of stock movements."""

    def setUp(self):
        self.user = User.objects.create_user("pharmacist", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Sarah Nakato", role=Staff.Role.PHARMACIST
        )
        self.client.login(username="pharmacist", password="TestPass123!")

        self.drug = Drug.objects.create(
            name="Amoxicillin",
            unit="tablet",
            stock_quantity=50,
            reorder_level=10,
            unit_price="0.50",
        )
        self.drug.restock(quantity=50, staff=self.staff, notes="Initial stock")
        self.patient = Patient.objects.create(
            full_name="Test Patient", sex="M", estimated_age=25
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.prescription = Prescription.objects.create(
            visit=self.visit,
            drug=self.drug,
            dosage="500mg",
            frequency="3 times a day",
            duration_days=7,
            quantity_prescribed=10,
        )
        self.drug.dispense(quantity=5, staff=self.staff, prescription=self.prescription)

    def test_movements_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:pharmacy_stock_movements"))
        self.assertEqual(response.status_code, 302)

    def test_movements_page_lists_entries(self):
        response = self.client.get(reverse("core:pharmacy_stock_movements"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amoxicillin")
        self.assertContains(response, "Dispense")
        self.assertContains(response, "Restock")

    def test_filter_by_dispense_type(self):
        response = self.client.get(
            reverse("core:pharmacy_stock_movements"), {"type": "dispense"}
        )
        self.assertEqual(response.status_code, 200)
        # Only the dispense movement (5 units) is shown, not the restock (50 units).
        self.assertContains(response, "5 tablet(s)")
        self.assertNotContains(response, "50 tablet(s)")

    def test_filter_by_restock_type(self):
        response = self.client.get(
            reverse("core:pharmacy_stock_movements"), {"type": "restock"}
        )
        self.assertEqual(response.status_code, 200)
        # Only the restock movement (50 units) is shown, not the dispense (5 units).
        self.assertContains(response, "50 tablet(s)")
        self.assertNotContains(response, "5 tablet(s)")


class InvoiceModelTests(TestCase):
    """UR-15 / UR-16 / FR-7 / FR-8: invoice generation and payment tracking."""

    def setUp(self):
        self.user = User.objects.create_user("cashier", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Mary Nakato", role=Staff.Role.RECEPTIONIST
        )
        self.patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.drug = Drug.objects.create(
            name="Amoxicillin",
            unit="tablet",
            stock_quantity=100,
            reorder_level=10,
            unit_price="0.50",
        )

    def test_generate_from_visit_creates_consultation_fee(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        self.assertIsNotNone(invoice.invoice_number)
        self.assertTrue(invoice.invoice_number.startswith("INV-"))
        self.assertEqual(invoice.total_amount, 5000)  # default consultation fee
        self.assertEqual(invoice.line_items.count(), 1)
        self.assertEqual(invoice.line_items.first().description, "Consultation fee")

    def test_generate_from_visit_includes_dispensed_drugs(self):
        # Dispense some drugs
        rx = Prescription.objects.create(
            visit=self.visit,
            drug=self.drug,
            dosage="500mg",
            frequency="3 times a day",
            duration_days=7,
            quantity_prescribed=21,
        )
        self.drug.dispense(quantity=10, staff=self.staff, prescription=rx)
        rx.quantity_dispensed = 10
        rx.save()

        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        # Consultation fee (5000) + 10 tablets * 0.50 = 5005
        self.assertEqual(invoice.total_amount, 5005)
        self.assertEqual(invoice.line_items.count(), 2)

    def test_generate_from_visit_returns_existing(self):
        invoice1 = Invoice.generate_from_visit(self.visit, staff=self.staff)
        invoice2 = Invoice.generate_from_visit(self.visit, staff=self.staff)
        self.assertEqual(invoice1.pk, invoice2.pk)
        self.assertEqual(Invoice.objects.count(), 1)

    def test_record_payment_full(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        payment = invoice.record_payment(
            amount=5000, method=Invoice.PaymentMethod.CASH, staff=self.staff
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 5000)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PAID)
        self.assertTrue(invoice.is_fully_paid)
        self.assertEqual(invoice.balance_due, 0)
        self.assertEqual(payment.method, Invoice.PaymentMethod.CASH)

    def test_record_payment_partial(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        invoice.record_payment(
            amount=2000, method=Invoice.PaymentMethod.MOBILE_MONEY, staff=self.staff
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 2000)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PARTIAL)
        self.assertEqual(invoice.balance_due, 3000)

    def test_record_payment_multiple_partials(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        invoice.record_payment(
            amount=2000, method=Invoice.PaymentMethod.CASH, staff=self.staff
        )
        invoice.record_payment(
            amount=3000, method=Invoice.PaymentMethod.MOBILE_MONEY, staff=self.staff
        )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 5000)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PAID)
        self.assertEqual(invoice.payments.count(), 2)

    def test_record_payment_exceeds_balance_raises(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        with self.assertRaises(ValueError):
            invoice.record_payment(
                amount=6000, method=Invoice.PaymentMethod.CASH, staff=self.staff
            )
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 0)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.UNPAID)

    def test_record_payment_zero_raises(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        with self.assertRaises(ValueError):
            invoice.record_payment(
                amount=0, method=Invoice.PaymentMethod.CASH, staff=self.staff
            )


class BillingDashboardTests(TestCase):
    """UR-15/UR-16/UR-18: billing landing page."""

    def setUp(self):
        self.user = User.objects.create_user("cashier", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Mary Nakato", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="cashier", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:billing_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_shows_summary(self):
        response = self.client.get(reverse("core:billing_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Billing & Payments")
        self.assertContains(response, "Nakato Aisha")

    def test_dashboard_shows_outstanding(self):
        response = self.client.get(reverse("core:billing_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Outstanding balances")
        self.assertContains(response, "5000")


class BillingInvoiceViewTests(TestCase):
    """UR-15/UR-16/UR-17: invoice generation, detail, payment, receipt."""

    def setUp(self):
        self.user = User.objects.create_user("cashier", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Mary Nakato", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="cashier", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        self.visit = Visit.objects.create(patient=self.patient)

    def test_generate_invoice_requires_login(self):
        self.client.logout()
        response = self.client.get(
            reverse("core:billing_invoice_generate", args=[self.visit.pk])
        )
        self.assertEqual(response.status_code, 302)

    def test_generate_invoice_creates_and_redirects(self):
        response = self.client.get(
            reverse("core:billing_invoice_generate", args=[self.visit.pk])
        )
        self.assertEqual(response.status_code, 302)
        invoice = Invoice.objects.get(visit=self.visit)
        self.assertRedirects(
            response, reverse("core:billing_invoice_detail", args=[invoice.pk])
        )

    def test_invoice_detail_page_loads(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        response = self.client.get(
            reverse("core:billing_invoice_detail", args=[invoice.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Consultation fee")
        self.assertContains(response, "Record payment")

    def test_record_payment_via_view(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        response = self.client.post(
            reverse("core:billing_invoice_detail", args=[invoice.pk]),
            {
                "amount": "5000",
                "method": "cash",
                "reference": "Receipt 001",
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 5000)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PAID)
        self.assertEqual(invoice.payments.count(), 1)
        self.assertEqual(invoice.payments.first().reference, "Receipt 001")

    def test_record_partial_payment_via_view(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        response = self.client.post(
            reverse("core:billing_invoice_detail", args=[invoice.pk]),
            {
                "amount": "2000",
                "method": "mobile_money",
                "reference": "MTN-12345",
            },
        )
        self.assertEqual(response.status_code, 302)
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 2000)
        self.assertEqual(invoice.payment_status, Invoice.PaymentStatus.PARTIAL)
        self.assertEqual(invoice.balance_due, 3000)

    def test_cannot_pay_more_than_balance(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        response = self.client.post(
            reverse("core:billing_invoice_detail", args=[invoice.pk]),
            {
                "amount": "6000",
                "method": "cash",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "exceeds the outstanding balance")
        invoice.refresh_from_db()
        self.assertEqual(invoice.amount_paid, 0)

    def test_invoice_list_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:billing_invoice_list"))
        self.assertEqual(response.status_code, 302)

    def test_invoice_list_shows_invoices(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        response = self.client.get(reverse("core:billing_invoice_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, invoice.invoice_number)
        self.assertContains(response, "Nakato Aisha")

    def test_invoice_list_filter_by_status(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        invoice.record_payment(
            amount=5000, method=Invoice.PaymentMethod.CASH, staff=self.staff
        )
        response = self.client.get(
            reverse("core:billing_invoice_list"), {"status": "paid"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, invoice.invoice_number)

    def test_receipt_page_loads(self):
        invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        invoice.record_payment(
            amount=5000, method=Invoice.PaymentMethod.CASH, staff=self.staff
        )
        response = self.client.get(
            reverse("core:billing_invoice_receipt", args=[invoice.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Receipt")
        self.assertContains(response, "Nakato Aisha")
        self.assertContains(response, "5000")


class BillingDailySummaryTests(TestCase):
    """UR-18: daily collections summary."""

    def setUp(self):
        self.user = User.objects.create_user("cashier", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Mary Nakato", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="cashier", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha", sex="F", estimated_age=34
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.invoice = Invoice.generate_from_visit(self.visit, staff=self.staff)
        self.invoice.record_payment(
            amount=5000, method=Invoice.PaymentMethod.CASH, staff=self.staff
        )

    def test_daily_summary_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:billing_daily_summary"))
        self.assertEqual(response.status_code, 302)

    def test_daily_summary_shows_totals(self):
        response = self.client.get(reverse("core:billing_daily_summary"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Daily collections summary")
        self.assertContains(response, "5000")

    def test_daily_summary_shows_method_breakdown(self):
        response = self.client.get(reverse("core:billing_daily_summary"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cash")
        self.assertContains(response, "Mobile Money")


class PaymentFormTests(TestCase):
    """UR-16 / FR-8: payment form validation."""

    def setUp(self):
        self.patient = Patient.objects.create(
            full_name="Test Patient", sex="M", estimated_age=25
        )
        self.visit = Visit.objects.create(patient=self.patient)
        self.invoice = Invoice.generate_from_visit(self.visit)

    def test_balance_due_is_initial(self):
        form = PaymentForm(invoice=self.invoice)
        self.assertEqual(form.fields["amount"].initial, 5000)

    def test_valid_full_payment(self):
        form = PaymentForm(
            {"amount": "5000", "method": "cash"}, invoice=self.invoice
        )
        self.assertTrue(form.is_valid())

    def test_valid_partial_payment(self):
        form = PaymentForm(
            {"amount": "2000", "method": "mobile_money"}, invoice=self.invoice
        )
        self.assertTrue(form.is_valid())

    def test_rejects_more_than_balance(self):
        form = PaymentForm(
            {"amount": "6000", "method": "cash"}, invoice=self.invoice
        )
        self.assertFalse(form.is_valid())


class AppointmentModelTests(TestCase):
    """UR-24 / FR-10: Appointment model behaviour."""

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            estimated_age=34,
            phone_number="0772123456",
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            appointment_date=timezone.now() + timedelta(days=7),
            reason="Follow-up for malaria treatment review",
            status=Appointment.Status.SCHEDULED,
        )

    def test_is_upcoming(self):
        self.assertTrue(self.appointment.is_upcoming)
        self.appointment.status = Appointment.Status.ATTENDED
        self.assertFalse(self.appointment.is_upcoming)

    def test_can_send_reminder(self):
        self.assertTrue(self.appointment.can_send_reminder)
        # No phone number -> cannot remind
        self.appointment.patient.phone_number = ""
        self.appointment.patient.save()
        self.assertFalse(self.appointment.can_send_reminder)
        # Restore phone number
        self.appointment.patient.phone_number = "0772123456"
        self.appointment.patient.save()
        # Cancelled -> cannot remind
        self.appointment.status = Appointment.Status.CANCELLED
        self.assertFalse(self.appointment.can_send_reminder)

    def test_str(self):
        self.assertIn("Nakato Aisha", str(self.appointment))


class AppointmentFormTests(TestCase):
    """UR-24: appointment form validation."""

    def test_rejects_past_date(self):
        from django.utils import timezone
        from datetime import timedelta

        past = (timezone.now() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
        form = AppointmentForm(
            data={
                "appointment_date": past,
                "reason": "Review",
                "notes": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("must be in the future", form.errors["appointment_date"][0])

    def test_accepts_future_date(self):
        from django.utils import timezone
        from datetime import timedelta

        future = (timezone.now() + timedelta(days=3)).strftime("%Y-%m-%dT%H:%M")
        form = AppointmentForm(
            data={
                "appointment_date": future,
                "reason": "Follow-up",
                "notes": "Check BP",
            }
        )
        self.assertTrue(form.is_valid())


class AppointmentViewTests(TestCase):
    """UR-24 / FR-10: appointment scheduling views."""

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta

        self.user = User.objects.create_user("receptionist", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Rita Nansubuga", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="receptionist", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            estimated_age=34,
            phone_number="0772123456",
        )
        self.future_time = (timezone.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M")
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            appointment_date=timezone.now() + timedelta(days=7),
            reason="Follow-up",
            status=Appointment.Status.SCHEDULED,
            scheduled_by=self.staff,
        )

    def test_dashboard_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("core:appointment_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_shows_appointments(self):
        response = self.client.get(reverse("core:appointment_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nakato Aisha")

    def test_create_page_loads(self):
        response = self.client.get(
            reverse("core:appointment_create", args=[self.patient.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Schedule appointment")

    def test_create_schedules_appointment(self):
        response = self.client.post(
            reverse("core:appointment_create", args=[self.patient.pk]),
            {
                "appointment_date": self.future_time,
                "reason": "Follow-up for malaria",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Appointment.objects.count(), 2)  # setup + newly created

    def test_detail_shows_appointment(self):
        response = self.client.get(
            reverse("core:appointment_detail", args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nakato Aisha")
        self.assertContains(response, "Follow-up")

    def test_cancel_appointment(self):
        response = self.client.get(
            reverse("core:appointment_cancel", args=[self.appointment.pk])
        )
        self.assertRedirects(response, reverse("core:appointment_dashboard"))
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.CANCELLED)

    def test_mark_attended(self):
        response = self.client.get(
            reverse("core:appointment_mark_attended", args=[self.appointment.pk])
        )
        self.assertRedirects(response, reverse("core:appointment_dashboard"))
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.ATTENDED)


class AppointmentSMSReminderTests(TestCase):
    """UR-24 / FR-10: SMS reminder sending via Africa's Talking."""

    def setUp(self):
        from django.utils import timezone
        from datetime import timedelta

        self.user = User.objects.create_user("receptionist", password="TestPass123!")
        self.staff = Staff.objects.create(
            user=self.user, name="Rita Nansubuga", role=Staff.Role.RECEPTIONIST
        )
        self.client.login(username="receptionist", password="TestPass123!")

        self.patient = Patient.objects.create(
            full_name="Nakato Aisha",
            sex="F",
            estimated_age=34,
            phone_number="0772123456",
        )
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            appointment_date=timezone.now() + timedelta(days=7),
            reason="Follow-up",
            status=Appointment.Status.SCHEDULED,
            scheduled_by=self.staff,
        )

    def test_send_reminder_creates_sms_record(self):
        response = self.client.get(
            reverse("core:appointment_send_reminder", args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SMSReminder.objects.count(), 1)
        reminder = SMSReminder.objects.first()
        self.assertEqual(reminder.phone_number, "0772123456")
        self.assertIn("Nakato Aisha", reminder.message)
        # In simulated mode (no AT_API_KEY), status is "sent"
        self.assertIn(reminder.status, ["sent", "failed"])

    def test_send_reminder_updates_status_to_reminded(self):
        self.client.get(
            reverse("core:appointment_send_reminder", args=[self.appointment.pk])
        )
        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.REMINDED)

    def test_cannot_remind_without_phone(self):
        self.patient.phone_number = ""
        self.patient.save()
        response = self.client.get(
            reverse("core:appointment_send_reminder", args=[self.appointment.pk])
        )
        self.assertRedirects(
            response, reverse("core:appointment_detail", args=[self.appointment.pk])
        )
        self.assertEqual(SMSReminder.objects.count(), 0)

    def test_sms_service_simulated_success(self):
        result = send_sms("0772123456", "Test message")
        self.assertTrue(result["success"])
        self.assertEqual(result["message_id"], "SIMULATED")

    def test_build_reminder_message(self):
        message = build_reminder_message(self.appointment)
        self.assertIn("Nakato Aisha", message)
        self.assertIn("Follow-up", message)
        self.assertIn("Community Health Clinic", message)
