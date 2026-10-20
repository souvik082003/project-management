from django.core.management.base import BaseCommand
from assignments.services import mark_overdue_assignments


class Command(BaseCommand):
    help = "Transitions past-deadline 'In progress' assignments to 'Overdue'."

    def handle(self, *args, **options):
        self.stdout.write("Checking for overdue project assignments...")
        count = mark_overdue_assignments()
        self.stdout.write(
            self.style.SUCCESS(f"Successfully marked {count} assignment(s) as Overdue.")
        )
