from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import RegisterView, MeView, MyTokenObtainPairView, ProfileView, RiskProfileView

# write your urls here
urlpatterns = [
    path('token/', MyTokenObtainPairView.as_view()),       # login → access + refresh tokens
    path('token/refresh/', TokenRefreshView.as_view()),  # swap refresh for new access
    
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', MyTokenObtainPairView.as_view(), name='login'),
    
    path('profile/', ProfileView.as_view(), name='profile'),
    path('me/', MeView.as_view()),                       
    path('risk/', RiskProfileView.as_view(), name='risk-profile'),
]