from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from groups.models import Group, Membership
from contributions.models import Contribution, Payout
from contributions.risks import update_user_risk
from wallets.models import Wallet, WalletTransaction
from notifications.utils import notify, notify_group
from demo.models import DemoProfile
from demo.serializers import (
    TriggerTransferSerializer,
    SimulatePosPayinSerializer,
    ResetDemoSerializer,
    DemoGroupDataSerializer,
)
from demo.monnify import monnify_client

import logging

logger = logging.getLogger(__name__)
User = get_user_model()

FREQUENCY_MAP = {
    "monthly": "MONTHLY",
    "weekly": "WEEKLY",
    "daily": "DAILY",
    "biweekly": "BIWEEKLY",
}

STATUS_MAP = {
    "active": "ACTIVE",
    "open": "OPEN",
    "completed": "COMPLETED",
    "cancelled": "CANCELLED",
}


class DemoDataView(APIView):
    permission_classes = []

    def get(self, request, group_id):
        group = Group.objects.filter(code=group_id).first()
        if not group:
            return Response(
                {"error": f"Demo group '{group_id}' not found. Run seed_demo_data first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        memberships = Membership.objects.filter(
            group=group, is_active=True
        ).select_related("user").order_by("rotation_order")

        members = []
        for m in memberships:
            dp = DemoProfile.objects.filter(user=m.user, group_slug=group_id).first()
            contrib = Contribution.objects.filter(
                user=m.user, group=group, round_number=group.current_round
            ).first()

            member_status = "UNPAID"
            if contrib:
                if contrib.status == "paid":
                    member_status = "PAID"
                elif contrib.status == "missed":
                    dp_overdue = DemoProfile.objects.filter(
                        user=m.user, group_slug=group_id, days_overdue__gt=0
                    ).first()
                    member_status = "OVERDUE_FLAGGED" if dp_overdue else "MISSED"
                elif contrib.status == "late":
                    member_status = "LATE"
                else:
                    member_status = "UNPAID"

            members.append({
                "id": m.user.email.split("@")[0].replace(".", "-"),
                "name": m.user.full_name or m.user.username,
                "role": m.role.upper() if m.role else "MEMBER",
                "trust_score": dp.trust_score if dp else 50,
                "status": member_status,
                "payout_position": m.rotation_order,
                "is_current_winner": dp.is_current_winner if dp else False,
                "monnify_account_number": dp.monnify_account_number if dp else "",
                "monnify_bank_name": dp.monnify_bank_name if dp else "",
                "monnify_account_name": dp.monnify_account_name if dp else "",
                "offline_payin_code": dp.offline_payin_code if dp else "",
                "days_overdue": dp.days_overdue if dp else 0,
                "kyc_verified": dp.kyc_verified if dp else False,
                "bvn_match": dp.bvn_match if dp else "",
            })

        data = {
            "group_id": group_id,
            "name": group.name,
            "contribution_amount": float(group.contribution_amount),
            "frequency": FREQUENCY_MAP.get(
                group.contribution_frequency, "MONTHLY"
            ),
            "status": STATUS_MAP.get(group.status, "ACTIVE"),
            "current_cycle": group.current_round,
            "overall_health_score": self._compute_health_score(group, members),
            "members": members,
        }
        serializer = DemoGroupDataSerializer(data=data)
        if serializer.is_valid():
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _compute_health_score(self, group, members):
        paid = sum(1 for m in members if m["status"] == "PAID")
        total = len(members) if members else 1
        payment_rate = (paid / total) * 100

        avg_trust = sum(m["trust_score"] for m in members) / total if members else 50
        health = int((payment_rate * 0.6) + (avg_trust * 0.4))
        return min(100, max(0, health))


class TriggerTransferView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = TriggerTransferSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        group_id = serializer.validated_data["group_id"]
        user_id = serializer.validated_data["user_id"]

        group = Group.objects.filter(code=group_id).first()
        if not group:
            return Response({"error": f"Group '{group_id}' not found."},
                            status=status.HTTP_404_NOT_FOUND)

        email = user_id.replace("-", ".") + "@smartajo-demo.com"
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": f"User '{user_id}' not found."},
                            status=status.HTTP_404_NOT_FOUND)

        dp = DemoProfile.objects.filter(user=user, group_slug=group_id).first()
        if not dp or not dp.monnify_account_number:
            return Response({"error": "No Monnify reserved account configured."},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            contrib, created = Contribution.objects.get_or_create(
                user=user,
                group=group,
                round_number=group.current_round,
                defaults={
                    "amount": group.contribution_amount,
                    "due_date": timezone.now().date(),
                    "status": "paid",
                    "paid_at": timezone.now(),
                },
            )
            if contrib.status not in ("paid", "late"):
                contrib.status = "paid"
                contrib.paid_at = timezone.now()
                contrib.save()

            update_user_risk(user)

            payout_info = self._check_and_process_payout(group, group.current_round)

        payout_message = ""
        if payout_info:
            ref = f"DEMO-MONNIFY-{timezone.now().timestamp():.0f}"
            transfer_result = monnify_client.initiate_transfer(
                amount=float(payout_info["amount"]),
                destination_account_number="1234567890",
                destination_bank_code="035",
                transaction_reference=ref,
                narration=f"SmartAjo Demo Payout - Round {group.current_round}",
            )
            payout_message = (
                f"₦{float(payout_info['amount']):,.0f} Payout Auto-Disbursed "
                f"to {payout_info['recipient_name']}!"
            )

        return Response({
            "message": "Payment Received via Monnify Reserved Account! " + payout_message,
            "payout": payout_info,
            "transfer_result": "simulated",
        })

    def _check_and_process_payout(self, group, round_number):
        total_members = group.total_members
        paid_count = Contribution.objects.filter(
            group=group,
            round_number=round_number,
            status__in=["paid", "late"],
        ).count()

        if paid_count >= total_members:
            recipient_membership = Membership.objects.filter(
                group=group,
                rotation_order=round_number,
                is_active=True,
            ).first()

            if recipient_membership:
                payout_amount = float(group.contribution_amount) * total_members
                payout, created = Payout.objects.get_or_create(
                    group=group,
                    round_number=round_number,
                    defaults={
                        "recipient": recipient_membership.user,
                        "amount": payout_amount,
                        "status": "paid",
                        "paid_at": timezone.now(),
                    },
                )

                if created:
                    recipient_membership.has_received_payout = True
                    recipient_membership.save()

                    notify(
                        recipient_membership.user,
                        "payout",
                        "Payout Received!",
                        f"You received ₦{payout_amount:,.0f} from {group.name} (Demo).",
                    )
                    notify_group(
                        group,
                        "payout",
                        "Round Complete",
                        f"Round {round_number} of {group.name} is complete. "
                        f"{recipient_membership.user.get_full_name()} received the payout.",
                        exclude_user=recipient_membership.user,
                    )

                    if round_number >= group.max_members:
                        group.status = "completed"
                    else:
                        group.current_round += 1
                    group.save()

                return {
                    "amount": payout_amount,
                    "recipient_name": recipient_membership.user.get_full_name(),
                    "round_number": round_number,
                    "new_round": group.current_round,
                }
        return None


class SimulatePosPayinView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = SimulatePosPayinSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        group_id = serializer.validated_data["group_id"]
        user_id = serializer.validated_data["user_id"]
        payin_code = serializer.validated_data["payin_code"]

        group = Group.objects.filter(code=group_id).first()
        if not group:
            return Response({"error": f"Group '{group_id}' not found."},
                            status=status.HTTP_404_NOT_FOUND)

        email = user_id.replace("-", ".") + "@smartajo-demo.com"
        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"error": f"User '{user_id}' not found."},
                            status=status.HTTP_404_NOT_FOUND)

        dp = DemoProfile.objects.filter(user=user, group_slug=group_id).first()
        if not dp:
            return Response({"error": "User not part of this demo group."},
                            status=status.HTTP_400_BAD_REQUEST)

        if dp.offline_payin_code != payin_code:
            return Response({"error": "Invalid pay-in code."},
                            status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            contrib, created = Contribution.objects.get_or_create(
                user=user,
                group=group,
                round_number=group.current_round,
                defaults={
                    "amount": group.contribution_amount,
                    "due_date": timezone.now().date(),
                    "status": "paid",
                    "paid_at": timezone.now(),
                },
            )
            if contrib.status not in ("paid", "late"):
                contrib.status = "paid"
                contrib.paid_at = timezone.now()
                contrib.save()

            dp.trust_score = min(100, dp.trust_score + 6)
            dp.save()

            update_user_risk(user)

            payout_info = self._check_and_process_payout(group, group.current_round)

        return Response({
            "message": "Cash pay-in verified! Payment recorded successfully.",
            "new_trust_score": dp.trust_score,
            "payout": payout_info,
        })

    def _check_and_process_payout(self, group, round_number):
        total_members = group.total_members
        paid_count = Contribution.objects.filter(
            group=group,
            round_number=round_number,
            status__in=["paid", "late"],
        ).count()

        if paid_count >= total_members:
            recipient_membership = Membership.objects.filter(
                group=group,
                rotation_order=round_number,
                is_active=True,
            ).first()

            if recipient_membership:
                payout_amount = float(group.contribution_amount) * total_members
                payout, created = Payout.objects.get_or_create(
                    group=group,
                    round_number=round_number,
                    defaults={
                        "recipient": recipient_membership.user,
                        "amount": payout_amount,
                        "status": "paid",
                        "paid_at": timezone.now(),
                    },
                )

                if created:
                    recipient_membership.has_received_payout = True
                    recipient_membership.save()

                    if round_number >= group.max_members:
                        group.status = "completed"
                    else:
                        group.current_round += 1
                    group.save()

                return {
                    "amount": payout_amount,
                    "recipient_name": recipient_membership.user.get_full_name(),
                    "round_number": round_number,
                    "new_round": group.current_round,
                }
        return None


class DemoResetView(APIView):
    permission_classes = []

    def post(self, request):
        serializer = ResetDemoSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        group_id = serializer.validated_data["group_id"]

        from django.core.management import call_command
        from io import StringIO

        out = StringIO()
        call_command("seed_demo_data", "--force", stdout=out)

        return Response({
            "message": f"Demo data reset successfully for group: {group_id}",
            "status": "reset_complete",
        })
