from django.core.management.base import BaseCommand
from assignments.services import send_deadline_reminders


class Command(BaseCommand):
    help = "Emails deadline reminder notifications to students whose project deadline is in 2 days."

    def handle(self, *args, **options):
        self.stdout.write("Checking for upcoming project deadlines (2-day window)...")
        count = send_deadline_reminders()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully dispatched {count} deadline reminder(s).")
        )
