from django.shortcuts import render
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers

from groups.models import Group, Membership
from .models import Contribution, Payout
from .serializers import ContributionSerializer, PayoutSerializer
from .risks import update_user_risk
from .squad import initiate_payment, verify_payment
from wallets.models import Wallet, WalletTransaction
        
# Create your views here.

@extend_schema(
    request=None,
    responses={
        200: inline_serializer(
            name='InitiateContributionResponse',
            fields={
                'message': serializers.CharField(),
                'checkout_url': serializers.URLField(),
                'transaction_ref': serializers.CharField(),
                'amount': serializers.DecimalField(max_digits=10, decimal_places=2),
            }
        ),
        403: inline_serializer(name='ForbiddenError', fields={'error': serializers.CharField()}),
        400: inline_serializer(name='BadRequestError', fields={'error': serializers.CharField()}),
    },
    summary="Initiate a contribution payment",
    tags=["Contributions"]
)
class InitiateContributionView(APIView):
    """
    Step 1 — user hits this endpoint to start payment.
    Returns a Squad checkout URL they visit to pay.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        method = request.query_params.get("method", "squad") 

        membership = Membership.objects.filter(
            user=request.user, group=group, is_active=True
        ).first()
        if not membership:
            return Response(
                {"error": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        if group.status != 'active':
            return Response(
                {"error": "This group is not currently active."},
                status=status.HTTP_400_BAD_REQUEST
            )

        already_paid = Contribution.objects.filter(
            user=request.user,
            group=group,
            round_number=group.current_round,
            status__in=['paid', 'late']
        ).exists()

        if already_paid:
            return Response(
                {"error": f"You have already paid for round {group.current_round}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = initiate_payment(request.user, group, group.contribution_amount)

        if not result['success']:
            return Response(
                {"error": result['error']},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Save a pending contribution so we can track it
        Contribution.objects.get_or_create(
            user=request.user,
            group=group,
            round_number=group.current_round,
            defaults={
                'amount': group.contribution_amount,
                'due_date': timezone.now().date(),
                'status': 'pending'
            }
        )

        if method == "squad":
            result = initiate_payment(request.user, group, group.contribution_amount)
            if not result['success']:
                return Response({"error": result['error']}, status=502)
            
            # Create the pending record so the webhook has something to find
            Contribution.objects.get_or_create(
                user=request.user, group=group, round_number=group.current_round,
                defaults={'amount': group.contribution_amount, 'due_date': timezone.now().date(), 'status': 'pending'}
            )
            return Response(result, status=200)

        elif method == "wallet":
            with transaction.atomic():
                wallet = get_object_or_404(Wallet, user=request.user)
                if wallet.balance < group.contribution_amount:
                    return Response({"error": "Insufficient funds"}, status=400)
                    
                wallet.balance -= group.contribution_amount
                wallet.save()


        # Record wallet transaction
        WalletTransaction.objects.create(
            wallet=wallet,
            type="contribution",
            amount=group.contribution_amount,
            status="success",
            description=f"Contribution to {group.name} — Round {group.current_round}"
        )

        # Mark contribution as paid
        contribution, _ = Contribution.objects.get_or_create(
            user=request.user,
            group=group,
            round_number=group.current_round,
            defaults={
                'amount': group.contribution_amount,
                'due_date': timezone.now().date(),
                'status': 'pending'
            }
        )
        contribution.status = 'paid'
        contribution.paid_at = timezone.now()
        contribution.save()

        update_user_risk(request.user)
        self._check_and_process_payout(group, group.current_round)


        return Response({
            "message": "Proceed to payment.",
            "checkout_url": result['checkout_url'],
            "transaction_ref": result['transaction_ref'],
            "amount": group.contribution_amount
        }, status=status.HTTP_200_OK)

@extend_schema(
    request=inline_serializer(
        name='SquadCallbackRequest',
        fields={'transaction_ref': serializers.CharField()}
    ),
    responses={
        200: inline_serializer(
            name='SquadCallbackResponse',
            fields={'message': serializers.CharField()}
        ),
    },
    summary="Squad payment webhook callback",
    tags=["Contributions"]
    )
class SquadCallbackView(APIView):
    """
    Step 2 — Squad hits this after payment is completed.
    This is your webhook endpoint — verify and record the payment.
    """
    permission_classes = []  # Squad hits this, not the user

    def post(self, request):
        transaction_ref = request.data.get('transaction_ref') or request.query_params.get('transaction_ref')

        if not transaction_ref:
            return Response({"error": "No transaction ref provided."}, status=status.HTTP_400_BAD_REQUEST)

        result = verify_payment(transaction_ref)

        if not result['success']:
            return Response({"error": result['error']}, status=status.HTTP_400_BAD_REQUEST)

        if result['status'] != 'success':
            return Response({"message": "Payment was not successful."}, status=status.HTTP_200_OK)

        # Extract metadata we stored during initiation
        metadata = result['metadata']
        user_id = metadata.get('user_id')
        group_id = metadata.get('group_id')
        round_number = metadata.get('round_number')

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            group = Group.objects.get(id=group_id)
        except Exception:
            return Response({"error": "User or group not found."}, status=status.HTTP_404_NOT_FOUND)

        # Update the contribution record
        contribution = Contribution.objects.filter(
            user=user, group=group, round_number=round_number
        ).first()

        if not contribution:
            return Response({"error": "Contribution record not found."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        contribution.status = 'late' if now.date() > contribution.due_date else 'paid'
        contribution.paid_at = now
        contribution.save()

        # Update risk score
        update_user_risk(user)

        # Check if round is complete
        self._check_and_process_payout(group, round_number)

        return Response({"message": "Payment confirmed."}, status=status.HTTP_200_OK)

    def _check_and_process_payout(self, group, round_number):
        total_members = group.total_members
        paid_count = Contribution.objects.filter(
            group=group,
            round_number=round_number,
            status__in=['paid', 'late']
        ).count()

        if paid_count >= total_members:
            recipient_membership = Membership.objects.filter(
                group=group,
                rotation_order=round_number,
                is_active=True
            ).first()

            if recipient_membership:
                payout_amount = group.contribution_amount * total_members
                Payout.objects.get_or_create(
                    group=group,
                    round_number=round_number,
                    defaults={
                        'recipient': recipient_membership.user,
                        'amount': payout_amount,
                        'status': 'paid',
                        'paid_at': timezone.now()
                    }
                )
                recipient_membership.has_received_payout = True
                recipient_membership.save()

                if round_number >= group.max_members:
                    group.status = 'completed'
                else:
                    group.current_round += 1
                group.save()

@extend_schema(
    request=None,
    responses={
        200: inline_serializer(
            name='MakeContributionResponse',
            fields={
                'message': serializers.CharField(),
                'status': serializers.CharField(),
                'your_risk_level': serializers.CharField(),
            }
        ),
        403: inline_serializer(name='MembershipError', fields={'error': serializers.CharField()}),
    },
    summary="Make a contribution for current round",
    tags=["Contributions"]
    )
class MakeContributionView(APIView):
    """User pays their contribution for the current round."""
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)

        # before allowing a contribution, 3 thingssss
        
        # Must be a member
        membership = Membership.objects.filter(
            user=request.user, group=group, is_active=True
        ).first()
        if not membership:
            return Response(
                {"error": "You are not a member of this group."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Group must be active
        if group.status != 'active':
            return Response(
                {"error": "This group is not currently active."},
                status=status.HTTP_400_BAD_REQUEST
            )

        round_number = group.current_round

        # Check if already paid this round
        already_paid = Contribution.objects.filter(
            user=request.user,
            group=group,
            round_number=round_number,
            status='paid'
        ).exists()

        if already_paid:
            return Response(
                {"error": f"You have already paid for round {round_number}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get or create the contribution record
        contribution, created = Contribution.objects.get_or_create(
            user=request.user,
            group=group,
            round_number=round_number,
            defaults={
                'amount': group.contribution_amount,
                'due_date': timezone.now().date(),
                'status': 'pending'
            }
        )

        # Mark as paid or late
        now = timezone.now()
        contribution.status = 'late' if now.date() > contribution.due_date else 'paid'
        contribution.paid_at = now
        contribution.amount = group.contribution_amount
        contribution.save()

        # Recalculate risk score
        update_user_risk(request.user)

        # Check if all members have paid this round → trigger payout
        self._check_and_process_payout(group, round_number)

        return Response({
            "message": f"Contribution of ₦{group.contribution_amount} recorded for round {round_number}.",
            "status": contribution.status,
            "your_risk_level": request.user.risk_level
        }, status=status.HTTP_200_OK)

    def _check_and_process_payout(self, group, round_number):
        """If all members paid, process the payout for this round."""
        total_members = group.total_members
        paid_count = Contribution.objects.filter(
            group=group,
            round_number=round_number,
            status__in=['paid', 'late']
        ).count()

        if paid_count >= total_members:
            # Find who receives payout this round
            recipient_membership = Membership.objects.filter(
                group=group,
                rotation_order=round_number,
                is_active=True
            ).first()

            if recipient_membership:
                payout_amount = group.contribution_amount * total_members
                Payout.objects.get_or_create(
                    group=group,
                    round_number=round_number,
                    defaults={
                        'recipient': recipient_membership.user,
                        'amount': payout_amount,
                        'status': 'paid',
                        'paid_at': timezone.now()
                    }
                )
                recipient_membership.has_received_payout = True
                recipient_membership.save()

                # Advance to next round or complete the group
                if round_number >= group.max_members:
                    group.status = 'completed'
                else:
                    group.current_round += 1
                group.save()


class GroupContributionsView(generics.ListAPIView):
    """All contributions for a specific group."""
    serializer_class = ContributionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        group_id = self.kwargs['group_id']
        return Contribution.objects.filter(group_id=group_id)


class MyContributionsView(generics.ListAPIView):
    """Logged-in user's full contribution history."""
    serializer_class = ContributionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Contribution.objects.filter(user=self.request.user)


@extend_schema(
    responses={
        200: inline_serializer(
            name='RoundSummaryResponse',
            fields={
                'group': serializers.CharField(),
                'current_round': serializers.IntegerField(),
                'total_rounds': serializers.IntegerField(),
                'pool_amount': serializers.DecimalField(max_digits=10, decimal_places=2),
                'payout_recipient': serializers.CharField(),
                'contributions': inline_serializer(
                    name='ContributionSummaryItem',
                    fields={
                        'user_id': serializers.IntegerField(),
                        'name': serializers.CharField(),
                        'rotation_order': serializers.IntegerField(),
                        'status': serializers.CharField(),
                        'paid_at': serializers.DateTimeField(),
                        'risk_level': serializers.CharField(),
                    },
                    many=True  # <-- tells Swagger it's a list
                ),
            }
        )
    },
    summary="Get round payment summary",
    tags=["Contributions"]
)
class RoundSummaryView(APIView):
    """Shows who paid and who hasn't for the current round."""
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        round_number = group.current_round
        members = Membership.objects.filter(group=group, is_active=True)

        summary = []
        for membership in members:
            contribution = Contribution.objects.filter(
                user=membership.user,
                group=group,
                round_number=round_number
            ).first()

            summary.append({
                "user_id": membership.user.id,
                "name": membership.user.get_full_name(),
                "rotation_order": membership.rotation_order,
                "status": contribution.status if contribution else "pending",
                "paid_at": contribution.paid_at if contribution else None,
                "risk_level": membership.user.risk_level,
            })

        # Find who receives payout this round
        payout_member = Membership.objects.filter(
            group=group,
            rotation_order=round_number
        ).first()

        return Response({
            "group": group.name,
            "current_round": round_number,
            "total_rounds": group.max_members,
            "pool_amount": group.pool_amount,
            "payout_recipient": payout_member.user.get_full_name() if payout_member else None,
            "contributions": summary
        })


class GroupPayoutsView(generics.ListAPIView):
    """Payout history for a group."""
    serializer_class = PayoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payout.objects.filter(group_id=self.kwargs['group_id'])