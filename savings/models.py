from django.db import models
from authentication.models import CustomUser
from groups.models import Group, Membership

# Create your models here.

class SavingsPlan(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='savings_plans')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='savings_plans', null=True, blank=True)
    membership = models.ForeignKey(Membership, on_delete=models.CASCADE, related_name='savings_plans', null=True, blank=True)

    name = models.CharField(max_length=100)
    expected_total = models.DecimalField(max_digits=10, decimal_places=2)
    contribution_per_cycle = models.DecimalField(max_digits=10, decimal_places=2)
    cycles_remaining = models.PositiveIntegerField()
    status = models.CharField(max_length=20, default='active') # e.g., "active", "completed", "paused"
    created_at = models.DateTimeField(auto_now_add=True)

class Transactions(models.Model):
    savings_plan = models.ForeignKey(SavingsPlan, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)