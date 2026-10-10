"""Small helpers for notifications and the activity log."""
from .models import ActivityLog, Notification


def notify(user, message, url=""):
    if user is None:
        return None
    return Notification.objects.create(user=user, message=message[:200], url=url[:200])


def log_activity(user, action, detail=""):
    actor = user if getattr(user, "is_authenticated", False) else None
    return ActivityLog.objects.create(user=actor, action=action[:80], detail=detail[:200])
