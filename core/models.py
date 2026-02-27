from django.db import models
from django.utils.crypto import get_random_string


class IFMISResetRequest(models.Model):
    full_name = models.CharField(max_length=255)
    department = models.CharField(max_length=255)
    email = models.EmailField()
    uploaded_file = models.FileField(upload_to="uploads/")
    submitted_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    reference_code = models.CharField(max_length=12, unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.reference_code:
            self.reference_code = get_random_string(12).upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.full_name} ({self.reference_code})"


class IFMISRequestMessage(models.Model):
    request = models.ForeignKey(IFMISResetRequest, on_delete=models.CASCADE, related_name="messages")
    sender = models.CharField(max_length=50)  # 'user' or 'admin'
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp']

    def __str__(self):
        return f"{self.sender}: {self.content[:20]}"