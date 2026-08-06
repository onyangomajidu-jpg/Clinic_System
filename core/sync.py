"""
Offline sync service (FR-12 / FR-13 / SDD 4.3).

Implements the sync strategy from SDD section 4.3:
- Each locally created/modified record carries `last_modified`, `synced`,
  and `origin_clinic_id` (already on SyncedModel).
- A background sync worker pushes unsynced records to the central server
  and pulls down shared reference data when connectivity is available.
- Conflict resolution follows last-write-wins (SDD 4.3).

This module provides the pure-Python sync logic used by both the Django
management command (`python manage.py sync`) and the API endpoint.
"""

import json
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from .models import (
    Appointment,
    Drug,
    Invoice,
    InvoiceLineItem,
    LabTest,
    Patient,
    Payment,
    Prescription,
    SMSReminder,
    Staff,
    StockMovement,
    Visit,
)

# Models that participate in sync, in dependency order (parents before children).
SYNC_MODELS = [
    Staff,
    Patient,
    Drug,
    Visit,
    Prescription,
    StockMovement,
    Invoice,
    InvoiceLineItem,
    Payment,
    LabTest,
    Appointment,
    SMSReminder,
]


def _serialize_record(instance):
    """Convert a model instance to a JSON-serialisable dict for sync."""
    data = {}
    for field in instance._meta.fields:
        value = getattr(instance, field.attname)
        if isinstance(value, datetime):
            value = value.isoformat()
        data[field.attname] = value
    return data


def _deserialize_record(model, data):
    """Convert a synced dict back into a model instance (not saved)."""
    instance = model()
    for field in model._meta.fields:
        attname = field.attname
        if attname not in data:
            continue
        value = data[attname]
        if isinstance(value, str) and field.get_internal_type() in (
            "DateTimeField",
            "DateField",
        ):
            try:
                value = datetime.fromisoformat(value)
            except ValueError:
                pass
        setattr(instance, attname, value)
    return instance


def get_unsynced_records(model, limit=100):
    """
    Return up to `limit` unsynced records for a model, oldest first.
    """
    return list(
        model.objects.filter(synced=False).order_by("last_modified")[:limit]
    )


def get_all_unsynced(limit_per_model=100):
    """
    Return all unsynced records grouped by model, in dependency order.
    """
    result = {}
    for model in SYNC_MODELS:
        records = get_unsynced_records(model, limit=limit_per_model)
        if records:
            result[model.__name__] = [_serialize_record(r) for r in records]
    return result


def push_unsynced(limit_per_model=100):
    """
    Simulate pushing unsynced records to the central server.

    In a real multi-clinic deployment this would POST to the central
    server's sync endpoint. For now, it marks records as synced and
    returns a summary of what was pushed.

    Returns a dict: {model_name: count_pushed}
    """
    pushed = {}
    for model in SYNC_MODELS:
        records = get_unsynced_records(model, limit=limit_per_model)
        if not records:
            continue
        with transaction.atomic():
            for record in records:
                record.synced = True
                record.save(update_fields=["synced", "last_modified"])
        pushed[model.__name__] = len(records)
    return pushed


def pull_updates(payload):
    """
    Apply updates received from the central server (last-write-wins).

    `payload` is a dict mapping model names to lists of record dicts.
    For each record, if the incoming last_modified is newer than the
    local one (or the record doesn't exist locally), it is saved.

    Returns a dict: {model_name: count_applied}
    """
    applied = {}
    model_map = {m.__name__: m for m in SYNC_MODELS}

    for model_name, records in payload.items():
        model = model_map.get(model_name)
        if model is None:
            continue
        count = 0
        for data in records:
            pk = data.get("id")
            if not pk:
                continue
            incoming_modified = data.get("last_modified")
            if isinstance(incoming_modified, str):
                try:
                    incoming_modified = datetime.fromisoformat(incoming_modified)
                except ValueError:
                    incoming_modified = None

            try:
                existing = model.objects.get(pk=pk)
            except model.DoesNotExist:
                existing = None

            if existing is not None and incoming_modified is not None:
                if existing.last_modified and existing.last_modified >= incoming_modified:
                    continue  # local is newer or equal -> skip

            instance = _deserialize_record(model, data)
            instance.synced = True
            instance.save()
            count += 1
        applied[model_name] = count

    return applied


def sync_all(limit_per_model=100):
    """
    Run a full sync cycle: push unsynced local records, then (in a real
    deployment) pull remote updates.

    Returns a summary dict with pushed and pulled counts.
    """
    pushed = push_unsynced(limit_per_model=limit_per_model)
    # In a real deployment, this would call the central server's API.
    # The pull_updates function is provided for the API endpoint to use.
    return {
        "pushed": pushed,
        "pulled": {},
        "timestamp": timezone.now().isoformat(),
    }