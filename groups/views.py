from django.shortcuts import render
from rest_framework.generics import ListCreateAPIView
import hashlib 
from django.conf import settings

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404

from .models import Group, Membership
from .serializers import GroupSerializer, CreateGroupSerializer, MemberSerializer

# Create your views here.
def index(request):
    return render(request, "index.html")

class CreateGroupView(generics.CreateAPIView):
    serializer_class = CreateGroupSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        group = serializer.save(admin=self.request.user)

        # Creator automatically joins as first member (rotation position 1)
        Membership.objects.create(
            user=self.request.user,
            group=group,
            rotation_order=1
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        group = Group.objects.get(name=serializer.data['name'], admin=request.user)
        return Response(
            GroupSerializer(group).data,
            status=status.HTTP_201_CREATED
        )


class ListGroupsView(generics.ListAPIView):
    """GET /api/groups/discover/ — only returns public open groups"""
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        # Returns only open groups the user hasn't joined
        joined_groups = self.request.user.memberships.values_list('group_id', flat=True)
        return Group.objects.filter(
            status='open',
            is_private=False        # only public groups in discover
            ).exclude(id__in=joined_groups)


class MyGroupsView(generics.ListAPIView):
    """All groups the logged-in user belongs to."""
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        joined_groups = self.request.user.memberships.values_list('group_id', flat=True)
        return Group.objects.filter(id__in=joined_groups)


class GroupDetailView(generics.RetrieveAPIView):
    serializer_class = GroupSerializer
    permission_classes = [IsAuthenticated]
    queryset = Group.objects.all()


class JoinGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)

        # Validations
        if group.status != 'open':
            return Response(
                {"error": "This group is no longer accepting members."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if group.is_full:
            return Response(
                {"error": "This group is full."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if Membership.objects.filter(user=request.user, group=group).exists():
            return Response(
                {"error": "You are already a member of this group."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if request.user.risk_level == 'high':
            return Response(
                {"error": "Your risk score is too high to join new groups."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Assign next rotation position
        next_position = group.total_members + 1
        Membership.objects.create(
            user=request.user,
            group=group,
            rotation_order=next_position
        )

        # If group is now full, move status to active
        if group.is_full:
            group.status = 'active'
            group.current_round = 1
            group.save()

        return Response(
            {"message": f"You have joined {group.name}. Your payout position is #{next_position}."},
            status=status.HTTP_200_OK
        )
    
class JoinGroupByCodeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        code = request.data.get('code', '').strip().upper()

        # check BEFORE normalizing
        if not code:
            return Response(
                {"error": "Group code is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # normalize — add AJO- if not already there
        if not code.startswith('AJO-'):
            code = f"AJO-{code}"

        # query ONCE
        group = Group.objects.filter(code=code).first()
        if not group:
            return Response(
                {"error": "Invalid group code. Please check and try again."},
                status=status.HTTP_404_NOT_FOUND
            )

        if group.status != 'open':
            return Response(
                {"error": "This group is no longer accepting members."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if group.is_full:
            return Response(
                {"error": "This group is full."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if Membership.objects.filter(user=request.user, group=group).exists():
            return Response(
                {"error": "You are already a member of this group."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if request.user.risk_level == 'high':
            return Response(
                {"error": "Your risk score is too high to join new groups."},
                status=status.HTTP_403_FORBIDDEN
            )

        next_position = group.total_members + 1
        Membership.objects.create(
            user=request.user,
            group=group,
            rotation_order=next_position
        )

        if group.is_full:
            group.status = 'active'
            group.current_round = 1
            group.save()

        return Response({
            "message": f"You joined {group.name} successfully!",
            "group": GroupSerializer(group).data,
            "your_position": next_position
        }, status=status.HTTP_200_OK)
    
class LeaveGroupView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        membership = get_object_or_404(Membership, user=request.user, group=group)

        if group.status == 'active':
            return Response(
                {"error": "You cannot leave an active group. Contact the group admin."},
                status=status.HTTP_400_BAD_REQUEST
            )

        membership.delete()
        return Response({"message": "You have left the group."}, status=status.HTTP_200_OK)


class GroupMembersView(generics.ListAPIView):
    """Lists all members of a group with their risk levels."""
    serializer_class = MemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        group = get_object_or_404(Group, pk=self.kwargs['pk'])
        return Membership.objects.filter(group=group, is_active=True)
    

class GroupInviteLinkView(APIView):
    """GET /api/groups/{id}/invite-link/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        group = get_object_or_404(Group, pk=pk)

        # Use the group's code directly
        invite_url = f"https://smartajo.app/join/{group.code}"

        return Response({
            "invite_link": invite_url,
            "code": group.code,
            "group_name": group.name
        })


class GroupHealthView(APIView):
    """GET /api/groups/{id}/health/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        group = get_object_or_404(Group, pk=pk)
        members = group.memberships.filter(is_active=True).select_related('user')
        total = members.count()

        if total == 0:
            return Response({
                "score": 100,
                "label": "Excellent",
                "details": "No members yet.",
                "breakdown": {}
            })

        from contributions.models import Contribution

        total_contributions = Contribution.objects.filter(group=group).count()
        missed = Contribution.objects.filter(group=group, status='missed').count()
        late = Contribution.objects.filter(group=group, status='late').count()
        paid = Contribution.objects.filter(group=group, status='paid').count()

        # Risk breakdown
        high_risk = sum(1 for m in members if m.user.risk_level == 'high')
        medium_risk = sum(1 for m in members if m.user.risk_level == 'medium')
        low_risk = sum(1 for m in members if m.user.risk_level == 'low')

        # Score — start at 100, deduct for issues
        score = 100
        if total_contributions > 0:
            miss_rate = missed / total_contributions
            late_rate = late / total_contributions
            score -= int(miss_rate * 60)   # missed payments hurt most
            score -= int(late_rate * 20)   # late payments hurt less
        score -= high_risk * 10            # each high risk member costs 10 points
        score -= medium_risk * 3           # each medium risk member costs 3 points
        score = max(0, min(100, score))    # clamp 0-100

        if score >= 80:
            label = "Excellent"
        elif score >= 60:
            label = "Good"
        elif score >= 40:
            label = "Fair"
        else:
            label = "At Risk"

        return Response({
            "score": score,
            "label": label,
            "details": f"{paid} on-time payments, {late} late, {missed} missed across {total} members.",
            "breakdown": {
                "total_members": total,
                "low_risk_members": low_risk,
                "medium_risk_members": medium_risk,
                "high_risk_members": high_risk,
                "total_contributions": total_contributions,
                "paid": paid,
                "late": late,
                "missed": missed
            }
        })