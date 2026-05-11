from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager, PermissionsMixin
from django.utils import timezone
import datetime

# Create your models here.

class CustomUserManager(BaseUserManager):
    def create_user(self, email, username, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, username, password=None, **extra_fields):
        extra_fields = extra_fields or {}
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, username, password, **extra_fields)
    
class CustomUser(AbstractUser, PermissionsMixin):
    RISK_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]

    email = models.EmailField(unique=True, max_length=150)
    username = models.CharField(max_length=150, unique=True)
    full_name = models.CharField(max_length=150, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
        
    # profile 
    display_name = models.CharField(max_length=150, blank=True)
    date_of_birth = models.DateField(null=True, blank=True, ) #related_name = "date_of_birth"
    nationality = models.CharField(max_length=100, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)

    objects = CustomUserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ['username', 'phone_number' ]

    # debit card details 


    # AI Risk fields
    risk_score = models.FloatField(default=0.0)  # 0-100
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default='low')
    total_contributions = models.PositiveIntegerField(default=0)
    missed_contributions = models.PositiveIntegerField(default=0)
    late_contributions = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False) 
        
    def __str__(self):
        return f"{self.get_full_name()} ({self.phone_number})"

    def update_risk_level(self):
        """Call this whenever risk_score changes."""
        if self.risk_score < 30:
            self.risk_level = 'low'
        elif self.risk_score < 70:
            self.risk_level = 'medium'
        else:
            self.risk_level = 'high'
        self.save()


class OTP(models.Model):
    phone_number = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def is_expired(self):
        return timezone.now() > self.created_at + datetime.timedelta(minutes=5)