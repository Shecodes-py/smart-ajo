from time import timezone

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
            group.start_date = timezone.now().date()  
            group.save()

            from contributions.models import Contribution
            from contributions.tasks import calculate_due_date
            due = calculate_due_date(group, group.start_date)
            for membership in group.memberships.filter(is_active=True):
                Contribution.objects.get_or_create(
                    user=membership.user,
                    group=group,
                    round_number=1,
                    defaults={
                        'amount': group.contribution_amount,
                        'status': 'pending',
                        'due_date': due
                    }
                )

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
    

class MemberProfileView(APIView):
    """GET /api/groups/{group_id}/members/{member_id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id, member_id):
        group = get_object_or_404(Group, pk=group_id)

        membership = get_object_or_404(
            Membership,
            group=group,
            user_id=member_id,
            is_active=True
        )

        user = membership.user

        # Full contribution history for this member in this group
        from contributions.models import Contribution
        contributions = Contribution.objects.filter(
            user=user,
            group=group
        ).order_by('round_number')

        contribution_data = [
            {
                "round_number": c.round_number,
                "amount": c.amount,
                "status": c.status,
                "paid_at": c.paid_at,
                "due_date": c.due_date,
            }
            for c in contributions
        ]

        return Response({
            "id": user.id,
            "full_name": user.full_name or user.get_full_name() or user.username,
            "email": user.email,
            "phone_number": user.phone_number,
            "risk_score": user.risk_score,
            "risk_level": user.risk_level,
            "rotation_order": membership.rotation_order,
            "has_received_payout": membership.has_received_payout,
            "joined_at": membership.joined_at,
            "total_contributions": contributions.count(),
            "paid_count": contributions.filter(status='paid').count(),
            "late_count": contributions.filter(status='late').count(),
            "missed_count": contributions.filter(status='missed').count(),
            "contributions": contribution_data
        })


class GroupPayoutsView(APIView):
    """GET /api/contributions/payouts/{group_id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        members = Membership.objects.filter(
            group=group, is_active=True
        ).select_related('user').order_by('rotation_order')

        total_rounds = group.total_rounds or group.max_members
        payout_amount = group.contribution_amount * group.total_members

        from datetime import timedelta
        frequency_days = {
            'daily': 1, 'weekly': 7,
            'biweekly': 14, 'monthly': 30
        }
        days_per_round = frequency_days.get(group.frequency, 7)

        # Build a map of existing paid payouts
        paid_payouts = {
            p.round_number: p
            for p in Payout.objects.filter(group=group)
        }

        # Build rotation map — position → member
        rotation_map = {m.rotation_order: m for m in members}

        schedule = []
        for round_num in range(1, total_rounds + 1):
            membership = rotation_map.get(round_num)
            existing_payout = paid_payouts.get(round_num)

            # Calculate payout date for this round
            if group.start_date:
                payout_date = group.start_date + timedelta(days=days_per_round * round_num)
            else:
                payout_date = None

            # Determine status
            if existing_payout and existing_payout.status == 'paid':
                status = 'paid'
            elif round_num == group.current_round:
                status = 'upcoming'
            else:
                status = 'scheduled'

            schedule.append({
                'round_number': round_num,
                'recipient_name': membership.user.get_full_name() or membership.user.username if membership else 'TBD',
                'recipient_id': membership.user.id if membership else None,
                'amount': payout_amount,
                'payout_date': payout_date.isoformat() if payout_date else None,
                'status': status,
                'is_current_round': round_num == group.current_round
            })

        return Response({
            'group': group.name,
            'total_rounds': total_rounds,
            'payout_amount': payout_amount,
            'schedule': schedule
        })