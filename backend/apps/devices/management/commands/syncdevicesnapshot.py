from django.core.management.base import BaseCommand

from accounts.models import Account
from devices.services import DeviceDashboardService


class Command(BaseCommand):
    help = "Run a one-off device dashboard snapshot refresh."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            dest="email",
            default=None,
            help="可选：只刷新指定账户邮箱的设备快照。",
        )

    def handle(self, *args, **options):
        email = options.get("email")
        accounts = Account.objects.filter(email=email) if email else Account.objects.all()

        if email and not accounts.exists():
            self.stderr.write(self.style.ERROR(f"Account not found: {email}"))
            return

        if not accounts.exists():
            self.stdout.write(self.style.WARNING("No accounts found to refresh."))
            return

        refreshed_accounts = 0
        for account in accounts:
            payload = DeviceDashboardService.refresh(account=account, trigger="command")
            snapshot = payload["snapshot"]
            refreshed_accounts += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"[{account.email}] Device snapshot refreshed. rooms={len(snapshot['rooms'])} devices={len(snapshot['devices'])} anomalies={len(snapshot['anomalies'])} rules={len(snapshot['rules'])}"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"Refreshed device snapshots for {refreshed_accounts} account(s)."))
