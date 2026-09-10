from .models import ActivityLog


def log_activity(user, action, description=""):
    ActivityLog.objects.create(user=user, action=action, description=description)
