from rest_framework import serializers
from .models import CustomUser
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()

# write your serializers here
class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email       # custom claim
        token['username'] = user.username
        # token['role'] = 'admin' if user.is_staff else 'user'
        return token


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_again = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'password', 'password_again', 'full_name',
                   'phone_number')

    def validate(self, data):
        if data['password'] != data['password_again']:
            raise serializers.ValidationError("Passwords do not match.")
        return data
    
    def create(self, validated_data):
        validated_data.pop('password_again')
        user = User.objects.create_user(**validated_data)
        return user
    

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'full_name', 'email',
                  'phone_number', 'date_of_birth',
                  'risk_score', 'risk_level', 'total_contributions',
                  'missed_contributions', 'late_contributions', 'created_at']
        
        read_only_fields = ['risk_score', 'risk_level', 'total_contributions',
                            'missed_contributions', 'late_contributions', 'created_at']
        

class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['full_name', 'email', 'date_of_birth']