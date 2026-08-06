from django import forms

from .models import Drug, Invoice, InvoiceLineItem, Patient, Prescription, Visit


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


class VisitForm(forms.ModelForm):
    """
    UR-6 / UR-7 / FR-3: record a patient visit with vitals, complaint,
    diagnosis, and notes.

    Designed for minimal typing (SDD section 2 / NFR-3): the visit type is a
    dropdown, vitals are split into individual numeric fields (BP, pulse,
    temperature, weight) that map into the Visit.vitals JSON blob, and the
    diagnosis field offers a datalist of common diagnoses so a clinician can
    pick one instead of typing it (UR-7: "dropdowns for common diagnoses
    where possible").
    """

    # Vitals are stored as a JSON blob on Visit.vitals (SDD 5.2), but we
    # expose them as individual form fields so the UI stays simple and the
    # data is validated per-field. They are optional -- a quick triage visit
    # shouldn't be blocked because the scale is broken.
    blood_pressure = forms.CharField(
        required=False,
        label="Blood pressure",
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "e.g. 120/80",
                "inputmode": "numeric",
            }
        ),
    )
    pulse = forms.IntegerField(
        required=False,
        label="Pulse (bpm)",
        widget=forms.NumberInput(
            attrs={"class": "input", "placeholder": "e.g. 72", "min": 0, "max": 300}
        ),
    )
    temperature = forms.DecimalField(
        required=False,
        label="Temperature (°C)",
        max_digits=4,
        decimal_places=1,
        widget=forms.NumberInput(
            attrs={"class": "input", "placeholder": "e.g. 37.0", "step": "0.1"}
        ),
    )
    weight = forms.DecimalField(
        required=False,
        label="Weight (kg)",
        max_digits=5,
        decimal_places=1,
        widget=forms.NumberInput(
            attrs={"class": "input", "placeholder": "e.g. 65.0", "step": "0.1"}
        ),
    )

    # Common diagnoses seen in community clinics (UR-7). Used as a datalist
    # so the clinician can type or pick; the field itself is free text.
    COMMON_DIAGNOSES = [
        "Malaria",
        "Upper respiratory tract infection",
        "Pneumonia",
        "Diarrhoea",
        "Typhoid fever",
        "Urinary tract infection",
        "Hypertension",
        "Diabetes mellitus",
        "Anaemia",
        "Gastritis",
        "Skin infection",
        "Malnutrition",
        "Tuberculosis (suspected)",
        "HIV (suspected)",
        "Antenatal check-up",
        "Postnatal check-up",
        "Trauma / injury",
        "Other",
    ]

    class Meta:
        model = Visit
        fields = [
            "visit_type",
            "chief_complaint",
            "diagnosis",
            "notes",
            "status",
        ]
        widgets = {
            "visit_type": forms.Select(attrs={"class": "input"}),
            "chief_complaint": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "e.g. Fever and headache for 2 days",
                }
            ),
            "diagnosis": forms.TextInput(
                attrs={
                    "class": "input",
                    "list": "common-diagnoses",
                    "placeholder": "Type or pick a common diagnosis",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "input",
                    "rows": 3,
                    "placeholder": "Additional clinical notes (optional)",
                }
            ),
            "status": forms.Select(attrs={"class": "input"}),
        }

    def save(self, commit=True):
        """
        Persist the visit, folding the individual vitals fields into the
        Visit.vitals JSON blob (SDD 5.2) before saving.
        """
        visit = super().save(commit=False)
        vitals = {}
        for field, key in (
            ("blood_pressure", "bp"),
            ("pulse", "pulse"),
            ("temperature", "temperature"),
            ("weight", "weight"),
        ):
            value = self.cleaned_data.get(field)
            if value not in (None, ""):
                vitals[key] = str(value)
        visit.vitals = vitals
        if commit:
            visit.save()
        return visit


class PrescriptionForm(forms.ModelForm):
    """
    UR-8 / FR-4: clinician adds a prescription linked to pharmacy stock.

    The drug picker only shows drugs that currently have stock, so the
    clinician cannot unknowingly prescribe an out-of-stock medication. The
    available stock level is shown inline as help text for each drug.
    """

    class Meta:
        model = Prescription
        fields = [
            "drug",
            "dosage",
            "frequency",
            "duration_days",
            "quantity_prescribed",
        ]
        widgets = {
            "drug": forms.Select(attrs={"class": "input"}),
            "dosage": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. 500mg"}
            ),
            "frequency": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. 3 times a day"}
            ),
            "duration_days": forms.NumberInput(
                attrs={"class": "input", "placeholder": "e.g. 7", "min": 1}
            ),
            "quantity_prescribed": forms.NumberInput(
                attrs={"class": "input", "placeholder": "e.g. 21", "min": 1}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only offer drugs that are currently in stock (FR-4).
        self.fields["drug"].queryset = Drug.objects.filter(stock_quantity__gt=0)
        # Show available stock next to each drug name.
        self.fields["drug"].label_from_instance = (
            lambda drug: f"{drug.name} ({drug.stock_quantity} {drug.unit}s available)"
        )

    def clean_quantity_prescribed(self):
        quantity = self.cleaned_data["quantity_prescribed"]
        if quantity <= 0:
            raise forms.ValidationError("Quantity must be at least 1.")
        return quantity


class DispenseForm(forms.Form):
    """
    UR-11 / UR-12 / UR-14: pharmacist dispenses against a prescription.

    The quantity to dispense defaults to the remaining balance on the
    prescription, but can be reduced for partial dispensing (UR-14). The
    field is validated in the view against both the remaining prescription
    balance and the available drug stock.
    """

    quantity_to_dispense = forms.IntegerField(
        min_value=1,
        label="Quantity to dispense",
        widget=forms.NumberInput(attrs={"class": "input", "min": 1}),
    )

    def __init__(self, *args, prescription=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.prescription = prescription
        if prescription is not None:
            self.fields[
                "quantity_to_dispense"
            ].initial = prescription.remaining_quantity or 1
            self.fields["quantity_to_dispense"].widget.attrs["max"] = (
                prescription.remaining_quantity or 1
            )
            self.fields["quantity_to_dispense"].help_text = (
                f"Remaining on prescription: {prescription.remaining_quantity}. "
                f"Stock available: {prescription.drug.stock_quantity} {prescription.drug.unit}(s)."
            )

    def clean_quantity_to_dispense(self):
        quantity = self.cleaned_data["quantity_to_dispense"]
        if self.prescription is not None:
            if quantity > self.prescription.remaining_quantity:
                raise forms.ValidationError(
                    f"Cannot dispense more than the remaining "
                    f"{self.prescription.remaining_quantity} on this prescription."
                )
            if quantity > self.prescription.drug.stock_quantity:
                raise forms.ValidationError(
                    f"Only {self.prescription.drug.stock_quantity} "
                    f"{self.prescription.drug.unit}(s) in stock."
                )
        return quantity


class DrugForm(forms.ModelForm):
    """
    Pharmacy stock management: add or edit a drug (UR-13).
    """

    class Meta:
        model = Drug
        fields = [
            "name",
            "unit",
            "stock_quantity",
            "reorder_level",
            "unit_price",
            "expiry_date",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "unit": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. tablet, ml, vial"}
            ),
            "stock_quantity": forms.NumberInput(
                attrs={"class": "input", "min": 0}
            ),
            "reorder_level": forms.NumberInput(
                attrs={"class": "input", "min": 0}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "input", "min": 0, "step": "0.01"}
            ),
            "expiry_date": forms.DateInput(
                attrs={"class": "input", "type": "date"}, format="%Y-%m-%d"
            ),
        }


class RestockForm(forms.Form):
    """
    UR-13: pharmacist records a stock delivery / restock.

    Only the quantity and an optional note are needed -- the drug is already
    known from the view context, and the staff member is captured from the
    logged-in user (UR-10: fast, uncluttered workflow).
    """

    quantity = forms.IntegerField(
        min_value=1,
        label="Quantity received",
        widget=forms.NumberInput(attrs={"class": "input", "min": 1}),
    )
    notes = forms.CharField(
        required=False,
        label="Notes (optional)",
        widget=forms.TextInput(
            attrs={"class": "input", "placeholder": "e.g. Supplier delivery"}
        ),
    )


class PaymentForm(forms.Form):
    """
    UR-16 / FR-8: record a payment against an invoice.

    Supports cash and mobile money (UR-15 / UR-16). The amount defaults to
    the outstanding balance but can be reduced for partial payments. The
    staff member is captured from the logged-in user.
    """

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        label="Amount paid",
        widget=forms.NumberInput(attrs={"class": "input", "min": "0.01", "step": "0.01"}),
    )
    method = forms.ChoiceField(
        choices=Invoice.PaymentMethod.choices,
        label="Payment method",
        widget=forms.Select(attrs={"class": "input"}),
    )
    reference = forms.CharField(
        required=False,
        label="Reference (optional)",
        widget=forms.TextInput(
            attrs={
                "class": "input",
                "placeholder": "e.g. MTN transaction ID, receipt number",
            }
        ),
    )

    def __init__(self, *args, invoice=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.invoice = invoice
        if invoice is not None:
            self.fields["amount"].initial = invoice.balance_due
            self.fields["amount"].widget.attrs["max"] = str(invoice.balance_due)
            self.fields["amount"].help_text = (
                f"Outstanding balance: {invoice.balance_due}"
            )

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if self.invoice is not None and amount > self.invoice.balance_due:
            raise forms.ValidationError(
                f"Amount exceeds the outstanding balance of {self.invoice.balance_due}."
            )
        return amount


class InvoiceLineItemForm(forms.ModelForm):
    """
    UR-15: add a line item to an invoice (e.g. consultation fee, drug, lab).
    """

    class Meta:
        model = InvoiceLineItem
        fields = ["description", "quantity", "unit_price"]
        widgets = {
            "description": forms.TextInput(
                attrs={"class": "input", "placeholder": "e.g. Consultation fee"}
            ),
            "quantity": forms.NumberInput(attrs={"class": "input", "min": 1}),
            "unit_price": forms.NumberInput(
                attrs={"class": "input", "min": "0", "step": "0.01"}
            ),
        }
