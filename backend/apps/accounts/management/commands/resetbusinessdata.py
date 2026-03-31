from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Account
from comms.models import Mission
from devices.models import (
    DeviceAnomaly,
    DeviceAutomationRule,
    DeviceDashboardState,
    DeviceRoom,
    DeviceSnapshot,
)
from memory.models import ProactiveLog, UserProfile
from providers.models import PlatformAuth


class Command(BaseCommand):
    help = (
        "清空业务数据表中的记录，并清空账户表，但保留 Django 系统表、迁移表等基础系统数据。"
        " 默认只预览，传入 --execute 才会真正删除。"
    )

    business_models = (
        ("comms_mission", Mission),
        ("devices_anomaly", DeviceAnomaly),
        ("devices_automation_rule", DeviceAutomationRule),
        ("devices_snapshot", DeviceSnapshot),
        ("devices_room", DeviceRoom),
        ("devices_dashboard_state", DeviceDashboardState),
        ("memory_proactive_log", ProactiveLog),
        ("memory_user_profile", UserProfile),
        ("platform_auth", PlatformAuth),
        ("accounts_account", Account),
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            dest="email",
            default=None,
            help="可选：只清空指定账户邮箱关联的业务数据。",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="真正执行删除。默认仅预览将要清空的数据量。",
        )

    def _get_accounts(self, email: str | None):
        if email:
            return Account.objects.filter(email=email)
        return Account.objects.all()

    def _get_queryset(self, model, accounts):
        if model is Account:
            return accounts
        account_field_names = {field.name for field in model._meta.fields}
        if "account" in account_field_names:
            return model.objects.filter(account__in=accounts)
        return model.objects.none()

    def handle(self, *args, **options):
        email = options.get("email")
        execute = bool(options.get("execute"))
        accounts = self._get_accounts(email)

        if email and not accounts.exists():
            self.stderr.write(self.style.ERROR(f"Account not found: {email}"))
            return

        account_count = accounts.count()
        account_scope = f"账户 {email}" if email else f"全部账户（共 {account_count} 个）"

        self.stdout.write(f"Business data reset scope: {account_scope}")
        self.stdout.write("Preserved system tables: django_*, auth_*, sessions, migrations.")

        plan = []
        total_rows = 0
        for table_name, model in self.business_models:
            queryset = self._get_queryset(model, accounts)
            row_count = queryset.count()
            total_rows += row_count
            plan.append((table_name, queryset, row_count))
            self.stdout.write(f"  - {table_name}: {row_count} rows")

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run only. {total_rows} rows would be deleted. "
                    "Re-run with --execute to apply."
                )
            )
            return

        with transaction.atomic():
            deleted_total = 0
            for table_name, queryset, row_count in plan:
                if row_count == 0:
                    continue
                queryset.delete()
                deleted_total += row_count
                self.stdout.write(self.style.SUCCESS(f"Deleted {row_count} rows from {table_name}."))

        self.stdout.write(
            self.style.SUCCESS(
                f"Business data reset complete. Deleted {deleted_total} rows. "
                "Accounts and Django system tables were not touched."
            )
        )
