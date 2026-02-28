from django.db import models
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string


class IFMISResetRequest(models.Model):
    full_name     = models.CharField(max_length=255)
    department    = models.CharField(max_length=255)
    email         = models.EmailField()
    uploaded_file = models.FileField(upload_to='uploads/')
    submitted_at  = models.DateTimeField(auto_now_add=True)
    processed     = models.BooleanField(default=False)
    reference_code = models.CharField(max_length=12, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = get_random_string(12).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.reference_code})"


class IFMISRequestMessage(models.Model):
    request   = models.ForeignKey(IFMISResetRequest, on_delete=models.CASCADE, related_name='messages')
    sender    = models.CharField(max_length=50)  # 'user' or 'admin'
    content   = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.content[:40]}"


class AuditLog(models.Model):
    """
    Records every significant action performed by an admin.
    Immutable — no update or delete methods exposed.
    """

    # Action type constants
    ACTION_LOGIN            = 'LOGIN'
    ACTION_LOGOUT           = 'LOGOUT'
    ACTION_VIEW_REQUEST     = 'VIEW_REQUEST'
    ACTION_MARK_PROCESSED   = 'MARK_PROCESSED'
    ACTION_MARK_PENDING     = 'MARK_PENDING'
    ACTION_SEND_REPLY       = 'SEND_REPLY'
    ACTION_DELETE_REQUEST   = 'DELETE_REQUEST'
    ACTION_BULK_DELETE      = 'BULK_DELETE'

    ACTION_CHOICES = [
        (ACTION_LOGIN,          'Logged In'),
        (ACTION_LOGOUT,         'Logged Out'),
        (ACTION_VIEW_REQUEST,   'Viewed Request'),
        (ACTION_MARK_PROCESSED, 'Marked as Processed'),
        (ACTION_MARK_PENDING,   'Reverted to Pending'),
        (ACTION_SEND_REPLY,     'Sent Reply'),
        (ACTION_DELETE_REQUEST, 'Deleted Request'),
        (ACTION_BULK_DELETE,    'Bulk Deleted Requests'),
    ]

    admin        = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action       = models.CharField(max_length=30, choices=ACTION_CHOICES)
    # Reference code stored as plain text so log survives after request deletion
    ref_code     = models.CharField(max_length=12, blank=True, null=True)
    detail       = models.TextField(blank=True)   # extra context e.g. message preview
    ip_address   = models.GenericIPAddressField(null=True, blank=True)
    timestamp    = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.admin} — {self.action} {self.ref_code or ''}"

    # Prevent accidental modification
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("AuditLog entries are immutable and cannot be updated.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("AuditLog entries cannot be deleted.")