from django.apps import AppConfig


class DigitalConfig(AppConfig):

    default_auto_field = "django.db.models.BigAutoField"

    name = "digital"

    def ready(self):
        import digital.signals
