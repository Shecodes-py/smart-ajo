from django.db import models
from django.conf import settings

from authentication.models import CustomUser
import random
import string

# Create your models here.

def generate_group_code():
    """Generates a unique 8-character alphanumeric code e.g. AJO-X7K2P9"""
    characters = string.ascii_uppercase + string.digits
    code = ''.join(random.choices(characters, k=6))
    return f"AJO-{code}"

class Group(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("member", "Member"),
    )
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
    ]
    STATUS_CHOICES = [
            ('open', 'Open'),        # accepting members
            ('active', 'Active'),    # contributions ongoing
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
    ]

    name = models.CharField(max_length=100, unique=True)
    code =  models.CharField(max_length=10, unique=True, blank=True)
    description = models.TextField(blank=True)
    admin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='admin_groups')
    
    contribution_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    contribution_frequency = models.CharField(max_length=50, blank=True, choices=FREQUENCY_CHOICES)
    
    max_members = models.PositiveIntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    current_round = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)

    total_cycles = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    def __str__(self):
        return self.name
    
    @property
    def total_members(self):
        return self.memberships.filter(is_active=True).count()

    @property
    def is_full(self):
        return self.total_members >= self.max_members

    @property
    def pool_amount(self):
        return self.contribution_amount * self.total_members
    
    def save(self, *args, **kwargs):
        if not self.code:  
            code = generate_group_code()
            # keep regenerating if code already exists (collision safety)
            while Group.objects.filter(code=code).exists():
                code = generate_group_code()
            self.code = code
        super().save(*args, **kwargs)


class Membership(models.Model):
    _CHOICES = (
        ("private", "Private"),
        ("public", "Public"),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    
    role = models.CharField(max_length=50, blank=True) # e.g., "admin", "member"
    joined_at = models.DateTimeField(auto_now_add=True)
    rotation_order = models.PositiveIntegerField()  # position in payout queue
    has_received_payout = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'group']  # one membership per user per group
        ordering = ['rotation_order']

    def __str__(self):
        return f"{self.user} in {self.group} (position {self.rotation_order})"