from django.urls import path
from .views import NotificationListView, MarkNotificationReadView, MarkAllReadView

urlpatterns = [
    path('', NotificationListView.as_view(), name='notifications'),
    path('mark-all-read/', MarkAllReadView.as_view(), name='mark-all-read'),
    path('<int:pk>/', MarkNotificationReadView.as_view(), name='mark-read'),
]