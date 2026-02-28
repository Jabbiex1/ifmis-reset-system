from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import AuditLog


def get_client_ip(request):
    x_forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded:
        return x_forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


@receiver(user_logged_in)
def log_staff_login(sender, request, user, **kwargs):
    if not request:
        return

    if request.path != '/staff/login/':
        return

    if not user.groups.filter(name='IFMIS_ADMIN').exists():
        return

    AuditLog(
        admin=user,
        action=AuditLog.ACTION_LOGIN,
        detail=f"Logged in as {user.username}",
        ip_address=get_client_ip(request),
    ).save()
