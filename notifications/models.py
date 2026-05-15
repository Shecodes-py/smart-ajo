from django.db import models
from django.conf import settings

# Create your models here.

class Notification(models.Model):
    TYPE_CHOICES = [
        ('payment_due', 'Payment Due'),
        ('payment_received', 'Payment Received'),
        ('payout', 'Payout'),
        ('risk_alert', 'Risk Alert'),
        ('group_joined', 'Group Joined'),
        ('group_full', 'Group Full'),
        ('missed_payment', 'Missed Payment'),
        ('general', 'General'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='general')
    title = models.CharField(max_length=100)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} — {self.title}"