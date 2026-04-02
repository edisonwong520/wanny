from django.apps import AppConfig

class CommsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'comms'

    def ready(self):
        from utils.telemetry import initialize_telemetry

        initialize_telemetry()
