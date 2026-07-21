from rest_framework import serializers


class TriggerTransferSerializer(serializers.Serializer):
    group_id = serializers.CharField(required=True)
    user_id = serializers.CharField(required=True)


class SimulatePosPayinSerializer(serializers.Serializer):
    group_id = serializers.CharField(required=True)
    user_id = serializers.CharField(required=True)
    payin_code = serializers.CharField(required=True)


class ResetDemoSerializer(serializers.Serializer):
    group_id = serializers.CharField(required=True)


class DemoMemberSerializer(serializers.Serializer):
    id = serializers.CharField()
    name = serializers.CharField()
    role = serializers.CharField()
    trust_score = serializers.IntegerField()
    status = serializers.CharField()
    payout_position = serializers.IntegerField()
    is_current_winner = serializers.BooleanField(default=False)
    monnify_account_number = serializers.CharField(default="", allow_blank=True)
    monnify_bank_name = serializers.CharField(default="", allow_blank=True)
    monnify_account_name = serializers.CharField(default="", allow_blank=True)
    offline_payin_code = serializers.CharField(default="", allow_blank=True)
    days_overdue = serializers.IntegerField(default=0)
    kyc_verified = serializers.BooleanField(default=False)
    bvn_match = serializers.CharField(default="", allow_blank=True)


class DemoGroupDataSerializer(serializers.Serializer):
    group_id = serializers.CharField()
    name = serializers.CharField()
    contribution_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    frequency = serializers.CharField()
    status = serializers.CharField()
    current_cycle = serializers.IntegerField()
    overall_health_score = serializers.IntegerField()
    members = DemoMemberSerializer(many=True)
