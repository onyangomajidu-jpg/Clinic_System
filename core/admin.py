from django.contrib import admin

from .models import (
    Drug,
    Invoice,
    InvoiceLineItem,
    LabTest,
    Patient,
    Payment,
    Prescription,
    Staff,
    StockMovement,
    Visit,
)


class PrescriptionInline(admin.TabularInline):
    model = Prescription
    extra = 1
    autocomplete_fields = ["drug", "dispensed_by"]


class LabTestInline(admin.TabularInline):
    model = LabTest
    extra = 1


class InvoiceLineItemInline(admin.TabularInline):
    model = InvoiceLineItem
    extra = 1


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "patient_card_no", "sex", "phone_number", "village", "created_at")
    list_filter = ("sex", "blood_group", "district")
    search_fields = ("full_name", "phone_number", "patient_card_no", "next_of_kin_name")
    ordering = ("full_name",)


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "phone", "is_active", "user")
    list_filter = ("role", "is_active")
    search_fields = ("name", "phone", "user__username")
    autocomplete_fields = ["user"]


@admin.register(Drug)
class DrugAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "unit",
        "stock_quantity",
        "reorder_level",
        "unit_price",
        "expiry_date",
        "is_low_stock",
        "is_near_expiry",
    )
    list_filter = ("unit",)
    search_fields = ("name",)
    ordering = ("name",)

    @admin.display(boolean=True, description="Low stock")
    def is_low_stock(self, obj):
        return obj.is_low_stock

    @admin.display(boolean=True, description="Near expiry")
    def is_near_expiry(self, obj):
        return obj.is_near_expiry


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = ("patient", "visit_date", "visit_type", "attending_staff", "status")
    list_filter = ("visit_type", "status")
    search_fields = ("patient__full_name", "patient__patient_card_no", "diagnosis")
    autocomplete_fields = ["patient", "attending_staff"]
    date_hierarchy = "visit_date"
    inlines = [PrescriptionInline, LabTestInline]


@admin.register(Prescription)
class PrescriptionAdmin(admin.ModelAdmin):
    list_display = (
        "visit",
        "drug",
        "dosage",
        "frequency",
        "duration_days",
        "quantity_prescribed",
        "quantity_dispensed",
        "remaining_quantity",
        "dispensed_by",
    )
    list_filter = ("drug",)
    search_fields = ("visit__patient__full_name", "drug__name")
    autocomplete_fields = ["visit", "drug", "dispensed_by"]

    @admin.display(description="Remaining")
    def remaining_quantity(self, obj):
        return obj.remaining_quantity


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "drug",
        "movement_type",
        "quantity",
        "staff",
        "balance_after",
        "created_at",
    )
    list_filter = ("movement_type",)
    search_fields = ("drug__name", "staff__name")
    autocomplete_fields = ["drug", "prescription", "staff"]
    date_hierarchy = "created_at"


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = (
        "invoice_number",
        "patient",
        "visit",
        "total_amount",
        "amount_paid",
        "balance_due",
        "payment_method",
        "payment_status",
        "created_at",
    )
    list_filter = ("payment_method", "payment_status")
    search_fields = ("invoice_number", "patient__full_name", "patient__patient_card_no")
    autocomplete_fields = ["visit", "patient", "created_by"]
    inlines = [InvoiceLineItemInline]
    date_hierarchy = "created_at"

    @admin.display(description="Balance due")
    def balance_due(self, obj):
        return obj.balance_due


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("invoice", "amount", "method", "staff", "reference", "created_at")
    list_filter = ("method",)
    search_fields = ("invoice__invoice_number", "invoice__patient__full_name", "reference")
    autocomplete_fields = ["invoice", "staff"]
    date_hierarchy = "created_at"


@admin.register(LabTest)
class LabTestAdmin(admin.ModelAdmin):
    list_display = ("test_name", "visit", "status", "result_date")
    list_filter = ("status",)
    search_fields = ("test_name", "visit__patient__full_name")
    autocomplete_fields = ["visit"]
