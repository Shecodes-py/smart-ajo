from rest_framework import serializers
from .models import SavingsPlan, Transaction

# write your serializers here
class SavingsPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SavingsPlan
        fields = ['id', 'user', 'group', 'expected_total', 'contribution_per_cycle', 'cycles_remaining']

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = ['id', 'savings_plan', 'amount', 'transaction_date', 'description']

