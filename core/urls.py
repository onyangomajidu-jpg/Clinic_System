from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    # Patient registration / search
    path("patients/register/", views.patient_register, name="patient_register"),
    path("patients/search/", views.patient_search, name="patient_search"),
    path("patients/<uuid:pk>/card/", views.patient_card, name="patient_card"),
    path("patients/<uuid:pk>/visits/", views.patient_visits, name="patient_visits"),
    path("patients/<uuid:pk>/visits/new/", views.visit_create, name="visit_create"),
    path("visits/<uuid:pk>/", views.visit_detail, name="visit_detail"),
    # Prescriptions (linked to visits)
    path("visits/<uuid:pk>/prescriptions/new/", views.visit_prescription_create, name="visit_prescription_create"),
    # Pharmacy & Inventory
    path("pharmacy/", views.pharmacy_dashboard, name="pharmacy_dashboard"),
    path("pharmacy/drugs/", views.pharmacy_drug_list, name="pharmacy_drug_list"),
    path("pharmacy/drugs/new/", views.pharmacy_drug_create, name="pharmacy_drug_create"),
    path("pharmacy/drugs/<uuid:pk>/edit/", views.pharmacy_drug_edit, name="pharmacy_drug_edit"),
    path("pharmacy/drugs/<uuid:pk>/restock/", views.pharmacy_restock, name="pharmacy_restock"),
    path("pharmacy/dispense/<uuid:pk>/", views.pharmacy_dispense, name="pharmacy_dispense"),
    path("pharmacy/movements/", views.pharmacy_stock_movements, name="pharmacy_stock_movements"),
    # Billing & Payments
    path("billing/", views.billing_dashboard, name="billing_dashboard"),
    path("billing/invoices/", views.billing_invoice_list, name="billing_invoice_list"),
    path("billing/invoices/<uuid:pk>/", views.billing_invoice_detail, name="billing_invoice_detail"),
    path("billing/invoices/<uuid:pk>/receipt/", views.billing_invoice_receipt, name="billing_invoice_receipt"),
    path("billing/invoices/generate/<uuid:pk>/", views.billing_invoice_generate, name="billing_invoice_generate"),
    path("billing/daily-summary/", views.billing_daily_summary, name="billing_daily_summary"),
    # Appointments & SMS Reminders
    path("appointments/", views.appointment_dashboard, name="appointment_dashboard"),
    path("appointments/<uuid:pk>/", views.appointment_detail, name="appointment_detail"),
    path("appointments/<uuid:pk>/remind/", views.appointment_send_reminder, name="appointment_send_reminder"),
    path("appointments/<uuid:pk>/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("appointments/<uuid:pk>/attended/", views.appointment_mark_attended, name="appointment_mark_attended"),
    path("patients/<uuid:pk>/appointments/new/", views.appointment_create, name="appointment_create"),
]
