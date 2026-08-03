from django.core.management.base import BaseCommand

from accounts.signals import sync_role_groups


class Command(BaseCommand):
    help = (
        "Create/update the Django Group + Permissions for each clinic role "
        "(doctor, nurse, clinical_officer, pharmacist, receptionist, "
        "lab_technician, admin) from accounts.permissions.ROLE_PERMISSIONS. "
        "Runs automatically after every 'migrate', so this command is only "
        "needed to force a re-sync without running migrations."
    )

    def handle(self, *args, **options):
        sync_role_groups(sender=None)
        self.stdout.write(self.style.SUCCESS("Role groups and permissions synced."))
