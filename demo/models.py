from django.db import models
from django.conf import settings


class DemoProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='demo_profile'
    )
    group_slug = models.CharField(max_length=50, blank=True)
    trust_score = models.PositiveIntegerField(default=0)
    payout_position = models.PositiveIntegerField(default=0)
    is_current_winner = models.BooleanField(default=False)
    monnify_account_number = models.CharField(max_length=20, blank=True)
    monnify_bank_name = models.CharField(max_length=100, blank=True)
    monnify_account_name = models.CharField(max_length=200, blank=True)
    offline_payin_code = models.CharField(max_length=50, blank=True)
    days_overdue = models.PositiveIntegerField(default=0)
    kyc_verified = models.BooleanField(default=False)
    bvn_match = models.CharField(max_length=20, blank=True)
    is_demo_user = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.get_full_name()} (Demo: {self.group_slug})"
