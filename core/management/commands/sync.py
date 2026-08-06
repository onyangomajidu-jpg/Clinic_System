"""
Django management command to run an offline sync cycle (FR-13 / SDD 4.3).

Usage:
    python manage.py sync

Pushes unsynced local records to the central server and marks them synced.
In a real multi-clinic deployment this would also pull remote updates.
"""

from django.core.management.base import BaseCommand

from core.sync import sync_all


class Command(BaseCommand):
    help = "Sync unsynced local records to the central server."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum records to push per model per cycle (default: 100).",
        )

    def handle(self, *args, **options):
        limit = options["limit"]
        self.stdout.write(self.style.SUCCESS("Starting sync cycle..."))

        result = sync_all(limit_per_model=limit)

        pushed = result["pushed"]
        total_pushed = sum(pushed.values())

        if total_pushed == 0:
            self.stdout.write(self.style.SUCCESS("No unsynced records. All synced."))
        else:
            for model_name, count in pushed.items():
                self.stdout.write(f"  Pushed {count} {model_name} record(s)")
            self.stdout.write(
                self.style.SUCCESS(f"Sync complete: {total_pushed} record(s) pushed.")
            )