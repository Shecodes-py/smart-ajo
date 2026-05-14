from django.db import models
from authentication.models import CustomUser
from groups.models import Group, Membership

from django.conf import settings

# Create your models here.

class Contribution(models.Model):
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('missed', 'Missed'),
        ('late', 'Late'),
        ('pending', 'Pending'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contributions')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='contributions')
    
    round_number = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    paid_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        unique_together = ['user', 'group', 'round_number']  # one contribution per user per round
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} | {self.group} | Round {self.round_number} | {self.status}"


class Payout(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('skipped', 'Skipped'),  # if recipient is high risk
    ]

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='payouts')
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='payouts')
    
    round_number = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['group', 'round_number']

    def __str__(self):
        return f"{self.recipient} | {self.group} | Round {self.round_number} | {self.status}"