from rest_framework import serializers
from .models import SavedCard

class SavedCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavedCard
        fields = ['id', 'last4', 'brand', 'exp_month', 'exp_year', 'is_default', 'created_at']
        read_only_fields = ['__all__']