from django.urls import path
from .views import AddCardView, CardCallbackView, ListCardsView, DeleteCardView

urlpatterns = [
    path('add-card/', AddCardView.as_view(), name='add-card'),
    path('card/callback/', CardCallbackView.as_view(), name='card-callback'),
    path('cards/', ListCardsView.as_view(), name='list-cards'),
    path('cards/<int:pk>/', DeleteCardView.as_view(), name='delete-card'),
]