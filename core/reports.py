"""
Reporting & analytics service (UR-19 / UR-23 / FR-11 / SDD Module 7).

Provides aggregation functions for patient volumes, common diagnoses,
revenue summaries, and drug usage trends over selectable date ranges.
"""

from collections import Counter
from datetime import date, timedelta

from django.db.models import Count, Sum

from .models import Invoice, Payment, Patient, Prescription, Visit


def _parse_dates(start_date, end_date):
    """Normalise date inputs; default to the last 30 days."""
    if start_date is None:
        start_date = date.today() - timedelta(days=30)
    if end_date is None:
        end_date = date.today()
    return start_date, end_date


def patient_volume_report(start_date=None, end_date=None):
    """
    UR-19 / FR-11: patient volumes over a date range.

    Returns total_visits, unique_patients, new_patients, by_day, by_visit_type.
    """
    start_date, end_date = _parse_dates(start_date, end_date)

    visits = Visit.objects.filter(
        visit_date__date__gte=start_date, visit_date__date__lte=end_date
    )
    total_visits = visits.count()
    unique_patients = visits.values("patient").distinct().count()

    new_patients = Patient.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    ).count()

    daily = (
        visits.extra(select={"day": "date(visit_date)"})
        .values("day")
        .annotate(visits=Count("id"))
        .order_by("day")
    )
    by_day = [{"date": row["day"], "visits": row["visits"]} for row in daily]

    by_type = (
        visits.values("visit_type").annotate(count=Count("id")).order_by("-count")
    )
    by_visit_type = [
        {"visit_type": row["visit_type"], "count": row["count"]} for row in by_type
    ]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_visits": total_visits,
        "unique_patients": unique_patients,
        "new_patients": new_patients,
        "by_day": by_day,
        "by_visit_type": by_visit_type,
    }


def diagnosis_report(start_date=None, end_date=None, limit=10):
    """
    UR-19 / FR-11: most common diagnoses over a date range.

    Returns a list of {diagnosis, count} sorted by count descending.
    """
    start_date, end_date = _parse_dates(start_date, end_date)

    visits = Visit.objects.filter(
        visit_date__date__gte=start_date,
        visit_date__date__lte=end_date,
    ).exclude(diagnosis="")

    counter = Counter()
    for visit in visits.only("diagnosis"):
        for part in visit.diagnosis.replace(";", ",").replace("/", ",").split(","):
            diagnosis = part.strip()
            if diagnosis:
                counter[diagnosis] += 1

    return [
        {"diagnosis": diagnosis, "count": count}
        for diagnosis, count in counter.most_common(limit)
    ]


def revenue_report(start_date=None, end_date=None):
    """
    UR-19 / FR-11: revenue summary over a date range.

    Returns total_billed, total_collected, outstanding, invoice_count,
    payment_count, by_method, by_day.
    """
    start_date, end_date = _parse_dates(start_date, end_date)

    invoices = Invoice.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    )
    payments = Payment.objects.filter(
        created_at__date__gte=start_date, created_at__date__lte=end_date
    )

    total_billed = invoices.aggregate(total=Sum("total_amount"))["total"] or 0
    total_collected = payments.aggregate(total=Sum("amount"))["total"] or 0
    outstanding = total_billed - total_collected

    by_method_rows = (
        payments.values("method")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("-total")
    )
    by_method = [
        {"method": row["method"], "total": row["total"], "count": row["count"]}
        for row in by_method_rows
    ]

    daily_invoices = (
        invoices.extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(billed=Sum("total_amount"))
        .order_by("day")
    )
    daily_payments = (
        payments.extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(collected=Sum("amount"))
        .order_by("day")
    )
    daily_map = {}
    for row in daily_invoices:
        daily_map.setdefault(row["day"], {"date": row["day"], "billed": 0, "collected": 0})["billed"] = row["billed"]
    for row in daily_payments:
        daily_map.setdefault(row["day"], {"date": row["day"], "billed": 0, "collected": 0})["collected"] = row["collected"]
    by_day = sorted(daily_map.values(), key=lambda r: r["date"])

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_billed": total_billed,
        "total_collected": total_collected,
        "outstanding": outstanding,
        "invoice_count": invoices.count(),
        "payment_count": payments.count(),
        "by_method": by_method,
        "by_day": by_day,
    }


def drug_usage_report(start_date=None, end_date=None, limit=10):
    """
    UR-19 / FR-11: drug usage trends over a date range.

    Returns a list of {drug, quantity_dispensed, prescriptions, revenue}
    sorted by quantity dispensed descending.
    """
    start_date, end_date = _parse_dates(start_date, end_date)

    prescriptions = Prescription.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        quantity_dispensed__gt=0,
    ).select_related("drug")

    usage = {}
    for rx in prescriptions:
        drug_name = rx.drug.name
        entry = usage.setdefault(
            drug_name,
            {"drug": drug_name, "quantity_dispensed": 0, "prescriptions": 0, "revenue": 0},
        )
        entry["quantity_dispensed"] += rx.quantity_dispensed
        entry["prescriptions"] += 1
        entry["revenue"] += rx.quantity_dispensed * rx.drug.unit_price

    return sorted(usage.values(), key=lambda r: r["quantity_dispensed"], reverse=True)[:limit]
