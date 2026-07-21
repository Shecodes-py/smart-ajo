from django.db import models
from django.conf import settings

# Create your models here.
class SavedCard(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_cards'
    )
    token = models.CharField(max_length=255)
    last4 = models.CharField(max_length=4)
    brand = models.CharField(max_length=20)        # Visa, Mastercard
    exp_month = models.CharField(max_length=2)
    exp_year = models.CharField(max_length=4)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.brand} *{self.last4}"