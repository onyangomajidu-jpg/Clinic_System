from django import forms

from .models import Patient


class PatientRegistrationForm(forms.ModelForm):
    """
    UR-1 / FR-1: register a new patient with minimal mandatory fields.

    Per the URS, a patient may have no national ID or fixed address, so the
    only hard-required fields are name and sex. We also require at least one
    of date-of-birth OR estimated age, since age is needed for clinical
    context (UR-7) and many patients don't know their exact birth date
    (UR-1 / SDD section 2).

    The clinic-issued card number (UR-3) is generated automatically on save
    so the receptionist never has to type it.
    """

    class Meta:
        model = Patient
        fields = [
            "full_name",
            "date_of_birth",
            "estimated_age",
            "sex",
            "phone_number",
            "village",
            "parish",
            "district",
            "next_of_kin_name",
            "next_of_kin_phone",
            "blood_group",
        ]
        widgets = {
            "full_name": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "e.g. Nakato Aisha",
                    "autofocus": True,
                    "autocapitalize": "words",
                }
            ),
            "date_of_birth": forms.DateInput(
                attrs={"class": "input", "type": "date"}, format="%Y-%m-%d"
            ),
            "estimated_age": forms.NumberInput(
                attrs={"class": "input", "placeholder": "e.g. 34", "min": 0, "max": 130}
            ),
            "sex": forms.Select(attrs={"class": "input"}),
            "phone_number": forms.TextInput(
                attrs={
                    "class": "input",
                    "placeholder": "e.g. 0772 123456 (optional)",
                    "autocapitalize": "none",
                }
            ),
            "village": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. Kyebando (optional)"}
            ),
            "parish": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. Kisaasi (optional)"}
            ),
            "district": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. Kampala (optional)"}
            ),
            "next_of_kin_name": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. John Ssebunya (optional)"}
            ),
            "next_of_kin_phone": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. 0700 000000 (optional)"}
            ),
            "blood_group": forms.Select(attrs={"class": "input"}),
        }

    def clean(self):
        cleaned = super().clean()
        dob = cleaned.get("date_of_birth")
        age = cleaned.get("estimated_age")
        if not dob and not age:
            raise forms.ValidationError(
                "Please provide either the date of birth or an estimated age "
                "(many patients don't know their exact birth date)."
            )
        return cleaned

    def save(self, commit=True):
        """Assign a clinic-issued card number (UR-3) before saving."""
        patient = super().save(commit=False)
        if not patient.patient_card_no:
            patient.patient_card_no = self._next_card_number()
        if commit:
            patient.save()
        return patient

    @staticmethod
    def _next_card_number():
        """
        Generate the next clinic card number, e.g. CL-2026-0001.

        Uses the current year and the count of existing patients this year
        to keep numbers short and human-readable for clinic staff. The
        patient_card_no column is unique, so a retry loop guards against a
        rare race between two registrations at the same moment.
        """
        from datetime import date

        year = date.today().year
        base = Patient.objects.filter(created_at__year=year).count() + 1
        while True:
            candidate = f"CL-{year}-{base:04d}"
            if not Patient.objects.filter(patient_card_no=candidate).exists():
                return candidate
            base += 1