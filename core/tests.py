from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .forms import PatientRegistrationForm, VisitForm
from .models import Patient, Staff, Visit


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
