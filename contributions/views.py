from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.conf import settings

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
from .squad import initiate_payment, verify_payment, parse_transaction_ref
from wallets.models import Wallet, WalletTransaction
from notifications.utils import notify, notify_group

from django.contrib.auth import get_user_model
User = get_user_model()   

import logging

logger = logging.getLogger(__name__)    

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
    Returns a Squad checkout URL they visit to pay or handles immediate wallet deduction.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        method = request.query_params.get("method", "squad") 

        membership = Membership.objects.filter(
            user=request.user, group=group, is_active=True
        ).first()
        if not membership:
            return Response({"error": "You are not a member of this group."}, status=status.HTTP_403_FORBIDDEN)

        if group.status != 'active':
            return Response({"error": "This group is not currently active."}, status=status.HTTP_400_BAD_REQUEST)

        already_paid = Contribution.objects.filter(
            user=request.user,
            group=group,
            round_number=group.current_round,
            status__in=['paid', 'late']
        ).exists()

        if already_paid:
            return Response({"error": f"You have already paid for round {group.current_round}."}, status=status.HTTP_400_BAD_REQUEST)

        if method == "squad":
            result = initiate_payment(request.user, group, group.contribution_amount)
            if not result['success']:
                return Response({"error": result['error']}, status=status.HTTP_502_BAD_GATEWAY)

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
            return Response({
                "message": "Proceed to payment.",
                "checkout_url": result['checkout_url'],
                "transaction_ref": result['transaction_ref'],
                "amount": group.contribution_amount
            }, status=status.HTTP_200_OK)

        elif method == "wallet":
            with transaction.atomic():
                # Lock the group row to prevent race conditions during immediate wallet processing
                locked_group = Group.objects.select_for_update().get(pk=group.id)
                wallet = get_object_or_404(Wallet, user=request.user)

                if wallet.balance < locked_group.contribution_amount:
                    return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)
                    
                wallet.balance -= locked_group.contribution_amount
                wallet.save()

                WalletTransaction.objects.create(
                    wallet=wallet,
                    type="contribution",
                    amount=locked_group.contribution_amount,
                    status="success",
                    description=f"Contribution to {locked_group.name} — Round {locked_group.current_round}"
                )

                contribution, _ = Contribution.objects.get_or_create(
                    user=request.user,
                    group=locked_group,
                    round_number=locked_group.current_round,
                    defaults={
                        'amount': locked_group.contribution_amount,
                        'due_date': timezone.now().date()
                    }
                )
                contribution.status = 'paid'
                contribution.paid_at = timezone.now()
                contribution.save()

                notify(
                    request.user,
                    'payment_received',
                    'Contribution Recorded',
                    f'Your ₦{contribution.amount:,.0f} contribution to {locked_group.name} (Round {locked_group.current_round}) was received.'
                )

                update_user_risk(request.user)
                self._check_and_process_payout(locked_group, locked_group.current_round)

                return Response({
                    "message": f"Contribution of ₦{locked_group.contribution_amount} processed via wallet successfully.",
                    "status": "paid",
                    "amount": locked_group.contribution_amount
                }, status=status.HTTP_200_OK)

        return Response({"error": "Invalid payment method specified."}, status=status.HTTP_400_BAD_REQUEST)

    def _check_and_process_payout(self, group, round_number):
        # Fallback helper just in case an un-locked group object slips into this view method
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
                payout, created = Payout.objects.get_or_create(
                    group=group,
                    round_number=round_number,
                    defaults={
                        'recipient': recipient_membership.user,
                        'amount': payout_amount,
                        'status': 'paid',
                        'paid_at': timezone.now()
                    }
                )
                
                if created:
                    recipient_membership.has_received_payout = True
                    recipient_membership.save()

                    notify(
                        recipient_membership.user,
                        'payout',
                        '🎉 Payout Received!',
                        f'You received ₦{payout_amount:,.0f} from {group.name}.'
                    )
                    notify_group(
                        group,
                        'payout',
                        'Round Complete',
                        f'Round {round_number} of {group.name} is complete. {recipient_membership.user.get_full_name()} received the payout.',
                        exclude_user=recipient_membership.user
                    )

                    if round_number >= group.max_members:
                        group.status = 'completed'
                    else:
                        group.current_round += 1
                    group.save()


class SquadCallbackView(APIView):
    """
    GET  — Squad redirects the user's browser here after payment
    POST — Squad sends webhook confirmation (server to server)
    """
    permission_classes = []

    def get(self, request):
        """Browser redirect after Squad checkout."""
        transaction_ref = request.query_params.get('reference') or \
                          request.query_params.get('transaction_ref')
        
        logger.info(f"Received GET callback from Squad with transaction_ref: {transaction_ref}")

        if not transaction_ref:
            logger.warning("No transaction_ref found in GET callback from Squad.")
            # Redirect to failure page
            return redirect(f"{settings.FRONTEND_URL}/pages/payment-status.html?status=failed")

        result = verify_payment(transaction_ref)
        logger.info(f"Verification result for transaction_ref {transaction_ref}: {result}")

        if not result['success'] or result['status'] != 'success':
            logger.warning(f"Payment verification failed for transaction_ref: {transaction_ref}. Result: {result}")
            return redirect(
                f"{settings.FRONTEND_URL}/pages/payment-status.html"
                f"?status=failed&transaction_ref={transaction_ref}"
            )
        logger.info(f"Payment verified successfully for transaction_ref: {transaction_ref}")

        # Process the payment
        parsed = parse_transaction_ref(transaction_ref)
        if not parsed:
            return Response({"error": "Invalid transaction ref format."}, status=400)

        user_id = parsed['user_id']
        group_id = parsed['group_id']
        round_number = parsed['round_number']

        try:
            user = User.objects.get(id=user_id)
            group = Group.objects.get(id=group_id)
        except Exception:
            logger.error(f"User or Group not found for transaction_ref: {transaction_ref}. user_id: {user_id}, group_id: {group_id}")
            return redirect(f"{settings.FRONTEND_URL}/pages/payment-status.html?status=failed")

        contribution = Contribution.objects.filter(
            user=user, group=group, round_number=round_number
        ).first()

        if contribution and contribution.status not in ['paid', 'late']:
            now = timezone.now()
            contribution.status = 'late' if now.date() > contribution.due_date else 'paid'
            contribution.paid_at = now
            contribution.save()
            update_user_risk(user)
            self._check_and_process_payout(group, round_number)

        # Redirect to frontend success page
        return redirect(
            f"{settings.FRONTEND_URL}/pages/payment-status.html"
            f"?status=success"
            f"&transaction_ref={transaction_ref}"
            f"&group_id={group_id}"
        )

    def post(self, request):
        """Server-to-server webhook from Squad."""
        # 1. FIX: Squad webhooks wrap data inside a 'Body' object
        body_data = request.data.get('Body', {})
        transaction_ref = body_data.get('transaction_ref') or request.query_params.get('transaction_ref')

        if not transaction_ref:
            return Response({"error": "No transaction ref provided."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Call Squad's API to verify this transaction status independently
        result = verify_payment(transaction_ref)

        if not result['success']:
            return Response({"error": result['error']}, status=status.HTTP_400_BAD_REQUEST)

        if result['status'] != 'success':
            return Response({"message": "Payment was not successful."}, status=status.HTTP_200_OK)

        parsed = parse_transaction_ref(transaction_ref)
        if not parsed:
            return Response({"error": "Invalid transaction ref format."}, status=400)

        user_id = parsed['user_id']
        group_id = parsed['group_id']
        round_number = parsed['round_number']

        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = User.objects.get(id=user_id)
            group = Group.objects.get(id=group_id)
        except Exception:
            return Response({"error": "User or group not found."}, status=404)

        # 3. Consolidating database processing into a single atomic block
        try:
            with transaction.atomic():
                user = User.objects.get(id=user_id)
                # Lock the group row to safely manage current_round state mutations
                group = Group.objects.select_for_update().get(id=group_id)
                
                contribution = Contribution.objects.filter(
                    user=user, group=group, round_number=round_number
                ).first()

                if not contribution:
                    return Response({"error": "Contribution record not found."}, status=status.HTTP_404_NOT_FOUND)

                # Idempotency safety: Stop processing if already paid
                if contribution.status in ['paid', 'late']:
                    return Response({"message": "Payment already processed previously."}, status=status.HTTP_200_OK)

                # Record contribution status
                now = timezone.now()
                contribution.status = 'late' if now.date() > contribution.due_date else 'paid'
                contribution.paid_at = now
                contribution.save()

                # Trigger notifications and risk calculations
                notify(
                    user,
                    'payment_received',
                    'Contribution Recorded',
                    f'Your ₦{contribution.amount:,.0f} contribution to {group.name} (Round {round_number}) was received.'
                )
                update_user_risk(user)
                
                # Check if this contribution closes the round and triggers an Ajo payout
                self._check_and_process_payout(group, round_number)

        except (User.DoesNotExist, Group.DoesNotExist):
            return Response({"error": "User or group not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": f"An error occurred: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
                payout, created = Payout.objects.get_or_create(
                    group=group,
                    round_number=round_number,
                    defaults={
                        'recipient': recipient_membership.user,
                        'amount': payout_amount,
                        'status': 'paid',
                        'paid_at': timezone.now()
                    }
                )
                
                if created:
                    recipient_membership.has_received_payout = True
                    recipient_membership.save()

                    notify(
                        recipient_membership.user,
                        'payout',
                        '🎉 Payout Received!',
                        f'You received ₦{payout_amount:,.0f} from {group.name}.'
                    )
                    notify_group(
                        group,
                        'payout',
                        'Round Complete',
                        f'Round {round_number} of {group.name} is complete. {recipient_membership.user.get_full_name()} received the payout.',
                        exclude_user=recipient_membership.user
                    )

                    if round_number >= group.max_members:
                        group.status = 'completed'
                    else:
                        group.current_round += 1
                    group.save()


class MakeContributionView(APIView):
    """User pays their contribution for the current round."""
    permission_classes = [IsAuthenticated]

    def post(self, request, group_id):
        # We also lock the group here during direct simulation changes
        with transaction.atomic():
            group = Group.objects.select_for_update().get(pk=group_id)

            membership = Membership.objects.filter(
                user=request.user, group=group, is_active=True
            ).first()
            if not membership:
                return Response({"error": "You are not a member of this group."}, status=status.HTTP_403_FORBIDDEN)

            if group.status != 'active':
                return Response({"error": "This group is not currently active."}, status=status.HTTP_400_BAD_REQUEST)

            round_number = group.current_round

            already_paid = Contribution.objects.filter(
                user=request.user,
                group=group,
                round_number=round_number,
                status='paid'
            ).exists()

            if already_paid:
                return Response({"error": f"You have already paid for round {round_number}."}, status=status.HTTP_400_BAD_REQUEST)

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

            now = timezone.now()
            contribution.status = 'late' if now.date() > contribution.due_date else 'paid'
            contribution.paid_at = now
            contribution.amount = group.contribution_amount
            contribution.save()
            
            notify(
                request.user,
                'payment_received',
                'Contribution Recorded',
                f'Your ₦{contribution.amount:,.0f} contribution to {group.name} (Round {round_number}) was received.'
            )
            
            update_user_risk(request.user)
            self._check_and_process_payout(group, round_number)

        return Response({
            "message": f"Contribution of ₦{group.contribution_amount} recorded for round {round_number}.",
            "status": contribution.status,
            "your_risk_level": request.user.risk_level
        }, status=status.HTTP_200_OK)

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
                payout, created = Payout.objects.get_or_create(
                    group=group,
                    round_number=round_number,
                    defaults={
                        'recipient': recipient_membership.user,
                        'amount': payout_amount,
                        'status': 'paid',
                        'paid_at': timezone.now()
                    }
                )
                
                if created:
                    recipient_membership.has_received_payout = True
                    recipient_membership.save()

                    if round_number >= group.max_members:
                        group.status = 'completed'
                    else:
                        group.current_round += 1
                    group.save()


class GroupContributionsView(APIView):
    """GET /api/contributions/group/{group_id}/"""
    permission_classes = [IsAuthenticated]

    def get(self, request, group_id):
        group = get_object_or_404(Group, pk=group_id)
        current_round = request.query_params.get('round', group.current_round)

        # All members for this group
        members = Membership.objects.filter(
            group=group, is_active=True
        ).select_related('user')

        contributions = Contribution.objects.filter(
            group=group,
            round_number=current_round
        ).select_related('user')

        # Map user_id → contribution
        contrib_map = {c.user_id: c for c in contributions}

        result = []
        for membership in members:
            user = membership.user
            contrib = contrib_map.get(user.id)

            result.append({
                'user_id': user.id,
                'user_name': user.get_full_name() or user.username,
                'rotation_order': membership.rotation_order,
                'round_number': int(current_round),
                'status': contrib.status if contrib else 'pending',
                'amount': contrib.amount if contrib else group.contribution_amount,
                'paid_at': contrib.paid_at if contrib else None,
                'due_date': contrib.due_date if contrib else None,
                'risk_level': user.risk_level,
            })

        # Sort — paid first, then pending, then missed
        status_order = {'paid': 0, 'late': 1, 'pending': 2, 'missed': 3}
        result.sort(key=lambda x: status_order.get(x['status'], 99))

        paid_count = sum(1 for r in result if r['status'] in ['paid', 'late'])

        return Response({
            'group': group.name,
            'current_round': group.current_round,
            'total_rounds': group.total_rounds or group.max_members,
            'round': int(current_round),
            'paid_count': paid_count,
            'total_members': len(result),
            'contributions': result
        })

class MyContributionsView(generics.ListAPIView):
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
                    many=True
                ),
            }
        )
    },
    summary="Get round payment summary",
    tags=["Contributions"]
)
class RoundSummaryView(APIView):
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
    serializer_class = PayoutSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Payout.objects.filter(group_id=self.kwargs['group_id'])

class SeedContributionView(APIView):
    """
    Demo/seeding only — creates paid OR missed contribution records
    without touching Squad or the wallet.

    POST /api/contributions/seed/
    Body:
    {
        "user_id": 5,
        "group_id": 3,
        "round_number": 2,
        "status": "missed"        # "paid" | "missed" | "late"
    }

    Remove this endpoint (and its url) before going to production.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user_id     = request.data.get("user_id")
        group_id    = request.data.get("group_id")
        round_number = request.data.get("round_number")
        status_val  = request.data.get("status", "paid")

        # ── Basic validation ──────────────────────────────────
        if not all([user_id, group_id, round_number]):
            return Response(
                {"error": "user_id, group_id, and round_number are all required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if status_val not in ["paid", "missed", "late"]:
            return Response(
                {"error": "status must be one of: paid, missed, late."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user  = get_object_or_404(User, pk=user_id)
        group = get_object_or_404(Group, pk=group_id)

        # ── Must be a member ──────────────────────────────────
        if not Membership.objects.filter(user=user, group=group, is_active=True).exists():
            return Response(
                {"error": f"{user.get_full_name()} is not an active member of {group.name}."},
                status=status.HTTP_403_FORBIDDEN
            )

        # ── Create or update the contribution record ──────────
        contribution, created = Contribution.objects.update_or_create(
            user=user,
            group=group,
            round_number=round_number,
            defaults={
                "amount":   group.contribution_amount,
                "status":   status_val,
                "due_date": timezone.now().date(),
                "paid_at":  timezone.now() if status_val in ["paid", "late"] else None,
            }
        )

        # ── Recalculate this user's risk score ────────────────
        update_user_risk(user)

        return Response(
            {
                "message":      f"Seed record {'created' if created else 'updated'} successfully.",
                "user":         user.get_full_name(),
                "group":        group.name,
                "round_number": round_number,
                "status":       status_val,
                "risk_level":   user.risk_level,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )