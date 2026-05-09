from django.db import models
from authentication.models import CustomUser

# Create your models here.

class Group(models.Model):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("member", "Member"),
    )

    name = models.CharField(max_length=100, unique=True)
    code =  models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    admin = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='admin_groups')
    
    contribution_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # contribution_frequency = models.CharField(max_length=50, blank=True) # e.g., "weekly", "monthly"
    
    total_cycles = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
 
    def __str__(self):
        return self.name

class Membership(models.Model):
    _CHOICES = (
        ("private", "Private"),
        ("public", "Public"),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    role = models.CharField(max_length=50, blank=True) # e.g., "admin", "member"
    joined_at = models.DateTimeField(auto_now_add=True)
    max_membership = models.IntegerField(default=10) # Maximum number of members allowed in a group
    # status = models.CharField(max_length=20, choices=_CHOICES, default="private") 
    contribution_frequency = models.CharField(max_length=50, blank=True) # e.g., "weekly", "monthly"
      
    class Meta:
        unique_together = ('user', 'group')