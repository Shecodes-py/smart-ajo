from django.urls import path
from .views import (
    CreateGroupView, ListGroupsView, MyGroupsView,
    GroupDetailView, JoinGroupView, LeaveGroupView, GroupMembersView, JoinGroupByCodeView,
    GroupInviteLinkView, GroupHealthView
)

# wrte your urls here
urlpatterns = [
    path('create/', CreateGroupView.as_view(), name='create-group'),
    path('discover/', ListGroupsView.as_view(), name='discover-groups'),
    path('my-groups/', MyGroupsView.as_view(), name='my-groups'),
    path('<int:pk>/', GroupDetailView.as_view(), name='group-detail'),
    path('<int:pk>/join/', JoinGroupView.as_view(), name='join-group'),
    path('<int:pk>/leave/', LeaveGroupView.as_view(), name='leave-group'),
    path('<int:pk>/members/', GroupMembersView.as_view(), name='group-members'),
    path('join-by-code/', JoinGroupByCodeView.as_view(), name='join-by-code'),

    path('<int:pk>/invite-link/', GroupInviteLinkView.as_view(), name='invite-link'),
    path('<int:pk>/health/', GroupHealthView.as_view(), name='group-health'),
]