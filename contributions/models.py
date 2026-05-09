from django.db import models
from authentication.models import CustomUser
from groups.models import Group, Membership

# Create your models here.

class Contribution(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='contributions')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='contributions')
    round_number = models.PositiveIntegerField()
    status = models.CharField(max_length=20)  # e.g., "paid", "missed", "late"
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.group.name} - Round {self.round_number} - {self.status}"
    