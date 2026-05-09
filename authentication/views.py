from django.shortcuts import render
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny 
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import RegisterSerializer, UserProfileSerializer, UpdateProfileSerializer, MyTokenObtainPairSerializer

from django.contrib.auth import get_user_model

User = get_user_model()

# Create your views here.
def index(request):
    return render(request, "index.html")

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

# POST /auth/register
class RegisterView(CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    queryset = User.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            "message": "Account created successfully.",
            "user": self.get_serializer(user).data
        }, status=status.HTTP_201_CREATED)
    

# POST /auth/login

# POST /auth/logout

# POST /auth/forgot-password
 
# POST /auth/verify-otp

# POST /auth/reset-password

# GET  /auth/me
class MeView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer
    queryset = User.objects.all()   

    def get(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class ProfileView(RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserProfileSerializer

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UpdateProfileSerializer
        return UserProfileSerializer

    def get_object(self):
        return self.request.user


class RiskProfileView(RetrieveAPIView):
    """Returns just the AI risk data for a user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "risk_score": user.risk_score,
            "risk_level": user.risk_level,
            "total_contributions": user.total_contributions,
            "missed_contributions": user.missed_contributions,
            "late_contributions": user.late_contributions,
            "payment_rate": self._payment_rate(user)
        })

    def _payment_rate(self, user):
        if user.total_contributions == 0:
            return 100.0
        paid = user.total_contributions - user.missed_contributions
        return round((paid / user.total_contributions) * 100, 1)