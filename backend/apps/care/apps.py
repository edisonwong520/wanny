from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _seed_system_rules(**kwargs):
    from care.defaults import seed_system_rules

    seed_system_rules()


class CareConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "care"
    verbose_name = "Proactive Care"

    def ready(self):
        post_migrate.connect(
            _seed_system_rules,
            sender=self,
            dispatch_uid="care.seed_system_rules",
        )
