from rest_framework import serializers
from .models import Group, Membership
from django.contrib.auth import get_user_model

User = get_user_model()

# write your serializers here
class MemberSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    phone_number = serializers.CharField(source='user.phone_number', read_only=True)
    risk_level = serializers.CharField(source='user.risk_level', read_only=True)
    risk_score = serializers.FloatField(source='user.risk_score', read_only=True)

    class Meta:
        model = Membership
        fields = [
            'id', 'user_id','group', 'role', 'full_name', 'phone_number',
            'rotation_order', 'has_received_payout',
            'risk_level', 'risk_score', 'joined_at'
        ]


class GroupSerializer(serializers.ModelSerializer):
    admin = serializers.CharField(source='admin.get_full_name', read_only=True)
    total_members = serializers.IntegerField(read_only=True)
    pool_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    members = MemberSerializer(source='memberships', many=True, read_only=True)

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'admin', 'code',
            'contribution_amount', 'contribution_frequency', 'max_members', 'status',
            'current_round', 'start_date', 'total_members', 'pool_amount', 'due_date',
            'is_full', 'members', 'created_at', 'is_private'
        ]
        read_only_fields = ['admin', 'status', 'current_round', 'code', 'created_at']


class CreateGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = [
            'name', 'description', 'contribution_amount', 'is_private',
            'contribution_frequency', 'max_members', 'start_date'
        ]

    def validate_max_members(self, value):
        if value < 2:
            raise serializers.ValidationError("A group needs at least 2 members.")
        if value > 50:
            raise serializers.ValidationError("Maximum 50 members per group.")
        return value

    def validate_contribution_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Contribution amount must be greater than 0.")
        return value