from django.core.management.base import BaseCommand

from devices.services import DeviceDashboardService


class Command(BaseCommand):
    help = "Run a one-off device dashboard snapshot refresh."

    def handle(self, *args, **options):
        payload = DeviceDashboardService.refresh(trigger="command")
        snapshot = payload["snapshot"]
        self.stdout.write(
            self.style.SUCCESS(
                f"Device snapshot refreshed. rooms={len(snapshot['rooms'])} devices={len(snapshot['devices'])} anomalies={len(snapshot['anomalies'])} rules={len(snapshot['rules'])}"
            )
        )
