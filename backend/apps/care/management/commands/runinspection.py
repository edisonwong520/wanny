from django.core.management.base import BaseCommand

from care.services.scanner import InspectionScanner


class Command(BaseCommand):
    help = "Run proactive care inspection scan immediately."

    def handle(self, *args, **options):
        created = InspectionScanner.scan_all_accounts()
        self.stdout.write(self.style.SUCCESS(f"Created {created} care suggestion(s)."))

