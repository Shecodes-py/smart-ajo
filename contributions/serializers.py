from rest_framework import serializers
from .models import Contribution, Payout

class ContributionSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = Contribution
        fields = [
            'id', 'user', 'user_name', 'group', 'group_name',
            'round_number', 'amount', 'status', 'paid_at',
            'due_date', 'created_at'
        ]
        read_only_fields = [
            'user', 'amount', 'status', 'paid_at',
            'round_number', 'created_at'
        ]


class PayoutSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(source='recipient.get_full_name', read_only=True)
    group_name = serializers.CharField(source='group.name', read_only=True)

    class Meta:
        model = Payout
        fields = [
            'id', 'group', 'group_name', 'recipient', 'recipient_name',
            'round_number', 'amount', 'status', 'paid_at', 'created_at'
        ]
        read_only_fields = ['__all__']