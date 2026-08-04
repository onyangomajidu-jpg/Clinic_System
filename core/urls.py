from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("patients/register/", views.patient_register, name="patient_register"),
    path("patients/search/", views.patient_search, name="patient_search"),
    path("patients/<uuid:pk>/card/", views.patient_card, name="patient_card"),
    path("patients/<uuid:pk>/visits/", views.patient_visits, name="patient_visits"),
    path("patients/<uuid:pk>/visits/new/", views.visit_create, name="visit_create"),
    path("visits/<uuid:pk>/", views.visit_detail, name="visit_detail"),
]