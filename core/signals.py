from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .notify import log_activity


@receiver(user_logged_in)
def record_login(sender, request, user, **kwargs):
    log_activity(user, "Logged in")
