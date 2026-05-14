from django.contrib import admin
from .models import Contribution, Payout

# Register your models here.

@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ['user', 'group', 'round_number', 'amount', 'status', 'due_date', 'paid_at']
    list_filter = ['status', 'group']
    search_fields = ['user__email', 'group__name']

@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ['recipient', 'group', 'round_number', 'amount', 'status', 'paid_at']
    list_filter = ['status', 'group']