from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Notification
from .serializers import NotificationSerializer

# Create your views here.
class NotificationListView(generics.ListAPIView):
    """GET /api/notifications/"""
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response({
            "notifications": serializer.data,
            "unread_count": queryset.filter(is_read=False).count()
        })


class MarkNotificationReadView(APIView):
    """PATCH /api/notifications/{id}/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(
            Notification, pk=pk, user=request.user
        )
        notification.is_read = True
        notification.save()
        return Response({"message": "Marked as read."}, status=status.HTTP_200_OK)


class MarkAllReadView(APIView):
    """PATCH /api/notifications/mark-all-read/"""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        Notification.objects.filter(
            user=request.user, is_read=False
        ).update(is_read=True)
        return Response({"message": "All notifications marked as read."})