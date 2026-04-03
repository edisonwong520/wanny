from django.core.management.base import BaseCommand

from comms.initial_keywords import iter_system_keyword_records
from comms.models import LearnedKeyword


class Command(BaseCommand):
    help = "Seed system keywords into LearnedKeyword as global source=system records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview how many system keywords would be created or updated without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = bool(options.get("dry_run"))
        created = 0
        updated = 0
        unchanged = 0

        for record in iter_system_keyword_records():
            lookup = {
                "account": None,
                "normalized_keyword": record["normalized_keyword"],
                "category": record["category"],
            }
            defaults = {
                "keyword": record["keyword"],
                "canonical": record["canonical"],
                "canonical_payload": record["canonical_payload"],
                "source": LearnedKeyword.SourceChoices.SYSTEM,
                "confidence": 1.0,
                "usage_count": 1,
                "is_active": True,
            }
            existing = LearnedKeyword.objects.filter(**lookup).first()
            if existing is None:
                created += 1
                if not dry_run:
                    LearnedKeyword.objects.create(**lookup, **defaults)
                continue

            has_changes = any(
                getattr(existing, field) != value
                for field, value in defaults.items()
                if field not in {"usage_count"}
            )
            if has_changes:
                updated += 1
                if not dry_run:
                    for field, value in defaults.items():
                        setattr(existing, field, value)
                    existing.save()
            else:
                unchanged += 1

        summary = (
            f"System keyword seed {'preview' if dry_run else 'complete'}: "
            f"created={created} updated={updated} unchanged={unchanged}"
        )
        self.stdout.write(self.style.SUCCESS(summary))
