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


class GroupAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'full_name']

class GroupSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    admin_id = serializers.IntegerField(source='created_by.id', read_only=True)  # add
    admin = GroupAdminSerializer(source='created_by', read_only=True)
    total_members = serializers.IntegerField(read_only=True)
    pool_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    target_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    is_full = serializers.BooleanField(read_only=True)
    members = MemberSerializer(source='memberships', many=True, read_only=True)
    due_date = serializers.SerializerMethodField()


    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'code',
            'created_by', 'created_by_name', 'admin_id', 'admin',
            'contribution_amount', 'contribution_frequency', 'max_members',
            'status', 'current_round', 'total_rounds',
            'start_date', 'end_date', 'due_date',
            'total_members', 'pool_amount', 'target_amount',
            'is_full', 'is_private', 'members', 'created_at'
        ]
        read_only_fields = [
            'created_by', 'status', 'current_round',
            'code', 'end_date', 'total_rounds'
        ]

    def get_due_date(self, obj):
        if not obj.start_date or obj.status != 'active':
            return None
        from datetime import timedelta
        frequency_days = {
            'daily': 1, 'weekly': 7,
            'biweekly': 14, 'monthly': 30
        }
        days = frequency_days.get(obj.frequency, 7)
        return (obj.start_date + timedelta(days=days * obj.current_round)).isoformat()

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if not data.get('contribution_frequency'):
            data['contribution_frequency'] = None
        return data

class CreateGroupSerializer(serializers.ModelSerializer):
    start_date = serializers.DateField(required=False, allow_null=True)
    duration = serializers.IntegerField(required=False, allow_null=True)
    
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

    def validate_frequency(self, value):
        valid = ['daily', 'weekly', 'biweekly', 'monthly']
        if not value or value not in valid:
            return None
        return value
    
    def validate(self, data):
        frequency = data.get('frequency')
        duration = data.get('duration')
        start_date = data.get('start_date')

        if frequency and duration and start_date:
            from datetime import timedelta
            frequency_days = {
                'daily': 1,
                'weekly': 7,
                'biweekly': 14,
                'monthly': 30
            }
            days = frequency_days.get(frequency, 7)
            data['end_date'] = start_date + timedelta(days=days * duration)
            data['total_rounds'] = duration
        elif duration:
            # no start_date yet — total_rounds still calculable
            data['total_rounds'] = duration

        return data