"""
Django management command to send SMS appointment reminders (UR-24 / FR-10).

Usage:
    python manage.py send_reminders [--days 1] [--dry-run]

Sends SMS reminders to patients with appointments in the next N days who
have not yet been reminded. Designed to be run by a cron/scheduled task
on the clinic server (or the central server in multi-clinic deployments).

Africa's Talking API credentials must be set (AT_API_KEY). Without them,
the command runs in simulated mode (messages are logged, not sent).
"""

from django.core.management.base import BaseCommand

from core.models import Appointment, SMSReminder
from core.services import build_reminder_message, send_sms


class Command(BaseCommand):
    help = "Send SMS reminders for upcoming appointments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=1,
            help="Send reminders for appointments within this many days (default: 1).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be sent without actually sending.",
        )
        parser.add_argument(
            "--status",
            default="scheduled",
            choices=["scheduled", "reminded"],
            help="Which appointment status to target (default: scheduled).",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]
        status = options["status"]

        from django.utils import timezone
        from datetime import timedelta

        cutoff = timezone.now() + timedelta(days=days)

        appointments = Appointment.objects.filter(
            appointment_date__lte=cutoff,
            appointment_date__gte=timezone.now(),
            status=status,
        ).select_related("patient")

        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for appointment in appointments:
            if not appointment.can_send_reminder:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  SKIP: {appointment} (no phone or not eligible)"
                    )
                )
                continue

            message = build_reminder_message(appointment)

            if dry_run:
                self.stdout.write(
                    f"  DRY-RUN: Would SMS {appointment.patient.phone_number}: {message}"
                )
                continue

            result = send_sms(appointment.patient.phone_number, message)

            SMSReminder.objects.create(
                appointment=appointment,
                phone_number=appointment.patient.phone_number,
                message=message,
                status="sent" if result["success"] else "failed",
                provider_message_id=result["message_id"],
                error_message=result["error"],
            )

            if result["success"]:
                appointment.status = Appointment.Status.REMINDED
                appointment.save(update_fields=["status", "last_modified"])
                sent_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  SENT: {appointment.patient.phone_number} - {message}"
                    )
                )
            else:
                failed_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"  FAILED: {appointment.patient.phone_number} - {result['error']}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: {sent_count} sent, {skipped_count} skipped, "
                f"{failed_count} failed"
            )
        )