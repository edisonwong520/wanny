from collections import Counter

from django.core.management.base import BaseCommand

from providers.clients.midea_cloud.mappings import audit_all_device_mappings


class Command(BaseCommand):
    help = "Audit translated Midea mappings for raw labels, raw option labels, and noisy status keys."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum number of issues to print.",
        )

    def handle(self, *args, **options):
        limit = max(1, int(options["limit"]))
        issues = audit_all_device_mappings()
        issue_counter = Counter(issue["issue"] for issue in issues)

        self.stdout.write(
            self.style.SUCCESS(
                f"Scanned Midea mappings: issues={len(issues)} "
                f"raw_label={issue_counter.get('raw_label', 0)} "
                f"raw_option_label={issue_counter.get('raw_option_label', 0)} "
                f"enum_without_options={issue_counter.get('enum_without_options', 0)} "
                f"raw_status_key_present={issue_counter.get('raw_status_key_present', 0)}"
            )
        )

        for issue in issues[:limit]:
            self.stdout.write(
                "[{severity}] T0x{device_type:02X} {entry} {control_key} {issue} {detail}".format(**issue)
            )

        if len(issues) > limit:
            self.stdout.write(f"... truncated {len(issues) - limit} additional issues")
