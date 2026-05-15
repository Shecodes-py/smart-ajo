from django.shortcuts import render
from django.db import transaction

from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView, ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated, AllowAny 
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken

from .utils import generate_otp, send_email_otp, store_otp, verify_otp
from .serializers import RegisterSerializer, UserProfileSerializer, UpdateProfileSerializer, MyTokenObtainPairSerializer

from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)

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
        
        # Generate and send OTP immediately after registration
    
        otp = generate_otp()
        store_otp(user.email, otp)
        logging.info(f"Generated OTP for {user.email}: {otp}")  # Log the OTP for debugging (remove in production)

        try:
            with transaction.atomic():
                send_email_otp(user.email, otp)
                message = "Account created. Check your email for the OTP."
                logging.info(f"Sent OTP email to {user.email}")
        except Exception as e:
            print(f"OTP ERROR: {e}")
            message = "Account created but email failed. Use /resend-otp/."
            logging.error(f"Failed to send OTP email to {user.email}: {e}")

        return Response({
            "message": message,
            "user_id": user.id,
            "phone_number": user.phone_number,
            "user": self.get_serializer(user).data
        }, status=status.HTTP_201_CREATED)
    
# POST /auth/verify-otp
class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_input = request.data.get('otp')

        if not email or not otp_input:
            return Response(
                {"error": "email and otp are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        is_valid, message = verify_otp(email, otp_input)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            user.is_verified = True
            user.save()
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({"message": message}, status=status.HTTP_200_OK)


class ResendOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        if user.is_verified:
            return Response({"message": "Account already verified."}, status=status.HTTP_200_OK)

        otp = generate_otp()
        store_otp(email, otp)

        try:
            send_email_otp(user.email, otp)
            return Response({"message": "OTP resent. Check your email."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Failed to send OTP."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# POST /auth/logout
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response({"message": "Successfully logged out."}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({"error": "Invalid token or refresh token required."}, status=status.HTTP_400_BAD_REQUEST)

# POST /auth/forgot-password
class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')

        if not email:
            return Response({"error": "email is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        otp = generate_otp()
        store_otp(email, otp)

        try:
            send_email_otp(user.email, otp)
            return Response({"message": "Password reset OTP sent. Check your email."}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Failed to send OTP."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# POST /auth/reset-password
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        otp_input = request.data.get('otp')
        new_password = request.data.get('password')

        if not all([email, otp_input, new_password]):
            return Response({"error": "Email, OTP, and new password are required."}, status=status.HTTP_400_BAD_REQUEST)

        is_valid, message = verify_otp(email, otp_input)
        if not is_valid:
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
            user.set_password(new_password) 
            user.save()
            return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

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
    """Returns just the risk data for a user."""
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