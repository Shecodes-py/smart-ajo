import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from groups.models import Group, Membership
from contributions.models import Contribution, Payout
from wallets.models import Wallet, WalletTransaction
from demo.models import DemoProfile

User = get_user_model()

DEMO_USERS = [
    # Tech Stars Thrift Pool
    {
        "id": "usr-01", "email": "amina.bello@smartajo-demo.com",
        "name": "Amina Bello", "username": "amina.bello",
        "role": "ADMIN", "trust_score": 98, "status": "PAID",
        "payout_position": 1, "is_current_winner": False,
        "group_slug": "techstars-01", "phone": "+2348010000001",
    },
    {
        "id": "usr-02", "email": "emeka.okafor@smartajo-demo.com",
        "name": "Emeka Okafor", "username": "emeka.okafor",
        "role": "MEMBER", "trust_score": 95, "status": "PAID",
        "payout_position": 2, "is_current_winner": False,
        "group_slug": "techstars-01", "phone": "+2348010000002",
    },
    {
        "id": "usr-03", "email": "tolu.adebayo@smartajo-demo.com",
        "name": "Tolu Adebayo", "username": "tolu.adebayo",
        "role": "MEMBER", "trust_score": 94, "status": "PAID",
        "payout_position": 3, "is_current_winner": True,
        "group_slug": "techstars-01", "phone": "+2348010000003",
    },
    {
        "id": "usr-04", "email": "fatima.usman@smartajo-demo.com",
        "name": "Fatima Usman", "username": "fatima.usman",
        "role": "MEMBER", "trust_score": 91, "status": "PAID",
        "payout_position": 4, "is_current_winner": False,
        "group_slug": "techstars-01", "phone": "+2348010000004",
    },
    {
        "id": "usr-05", "email": "kelechi.egwu@smartajo-demo.com",
        "name": "Kelechi Egwu (Demo Persona)", "username": "kelechi.egwu",
        "role": "MEMBER", "trust_score": 88, "status": "UNPAID",
        "payout_position": 5, "is_current_winner": False,
        "group_slug": "techstars-01", "phone": "+2348010000005",
        "monnify_account": {
            "account_number": "7820193841",
            "bank_name": "Wema Bank / Monnify",
            "account_name": "SmartAjo - Kelechi",
        },
    },
    # Balogun Traders Association
    {
        "id": "usr-06", "email": "mama.aisha@smartajo-demo.com",
        "name": "Mama Aisha", "username": "mama.aisha",
        "role": "ADMIN", "trust_score": 92, "status": "PAID",
        "payout_position": 1, "is_current_winner": False,
        "group_slug": "balogun-02", "phone": "+2348020000001",
    },
    {
        "id": "usr-07", "email": "chidi.trades@smartajo-demo.com",
        "name": "Chidi Trades", "username": "chidi.trades",
        "role": "MEMBER", "trust_score": 84, "status": "PAID",
        "payout_position": 2, "is_current_winner": False,
        "group_slug": "balogun-02", "phone": "+2348020000002",
    },
    {
        "id": "usr-08", "email": "ibrahim.garba@smartajo-demo.com",
        "name": "Ibrahim Garba", "username": "ibrahim.garba",
        "role": "MEMBER", "trust_score": 42, "status": "OVERDUE_FLAGGED",
        "payout_position": 3, "is_current_winner": False,
        "group_slug": "balogun-02", "phone": "+2348020000003",
        "risk_level": "HIGH_RISK", "days_overdue": 2,
        "kyc_verified": True, "bvn_match": "VERIFIED_MATCH",
    },
    {
        "id": "usr-09", "email": "blessing.okon@smartajo-demo.com",
        "name": "Blessing Okon", "username": "blessing.okon",
        "role": "MEMBER", "trust_score": 89, "status": "PAID",
        "payout_position": 4, "is_current_winner": False,
        "group_slug": "balogun-02", "phone": "+2348020000004",
    },
    {
        "id": "usr-10", "email": "nkechi.eze@smartajo-demo.com",
        "name": "Nkechi Eze (Demo Persona)", "username": "nkechi.eze",
        "role": "MEMBER", "trust_score": 76, "status": "UNPAID",
        "payout_position": 5, "is_current_winner": False,
        "group_slug": "balogun-02", "phone": "+2348020000005",
        "offline_payin_code": "SA-BALOGUN-05",
    },
]

DEMO_GROUPS = [
    {
        "slug": "techstars-01",
        "name": "Tech Stars Thrift Pool",
        "contribution_amount": 100000.00,
        "frequency": "MONTHLY",
        "status": "ACTIVE",
        "current_round": 3,
        "max_members": 5,
        "total_rounds": 5,
        "overall_health_score": 93,
    },
    {
        "slug": "balogun-02",
        "name": "Balogun Traders Association",
        "contribution_amount": 20000.00,
        "frequency": "WEEKLY",
        "status": "ACTION_REQUIRED",
        "current_round": 2,
        "max_members": 5,
        "total_rounds": 5,
        "overall_health_score": 58,
    },
]


def get_group_from_slug(slug):
    return Group.objects.filter(code=slug).first()


def map_frequency(freq):
    mapping = {
        "MONTHLY": "monthly",
        "WEEKLY": "weekly",
        "DAILY": "daily",
        "BIWEEKLY": "biweekly",
    }
    return mapping.get(freq, "monthly")


def map_status(status):
    mapping = {
        "ACTIVE": "active",
        "ACTION_REQUIRED": "active",
        "OPEN": "open",
        "COMPLETED": "completed",
        "CANCELLED": "cancelled",
    }
    return mapping.get(status, "active")


class Command(BaseCommand):
    help = "Seeds demo data for Smart Ajo demo experience"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Skip confirmation prompt",
        )

    def handle(self, *args, **options):
        force = options.get("force", False)

        if not force:
            self.stdout.write(
                self.style.WARNING(
                    "This will delete all existing demo data and re-seed. "
                    "Continue? [y/N]: "
                )
            )
            response = input().strip().lower()
            if response != "y":
                self.stdout.write(self.style.ERROR("Aborted."))
                return

        with transaction.atomic():
            self._clear_existing_demo_data()
            users = self._create_demo_users()
            groups = self._create_demo_groups(users)
            self._create_demo_memberships(users, groups)
            self._create_demo_contributions(users, groups)
            self._create_demo_wallets(users)
            self._create_demo_payouts(users, groups)

        self.stdout.write(
            self.style.SUCCESS(f"Demo data seeded successfully! "
                               f"{len(users)} users, {len(groups)} groups.")
        )

    def _clear_existing_demo_data(self):
        demo_emails = [u["email"] for u in DEMO_USERS]
        User.objects.filter(email__in=demo_emails).delete()
        self.stdout.write("Cleared existing demo data.")

    def _create_demo_users(self):
        users = {}
        for data in DEMO_USERS:
            risk_level_map = {"HIGH_RISK": "high"}
            user_risk_level = risk_level_map.get(
                data.get("risk_level", ""), "low"
            )

            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "username": data["username"],
                    "full_name": data["name"],
                    "phone_number": data.get("phone", ""),
                    "risk_score": 0.0,
                    "risk_level": user_risk_level,
                    "is_active": True,
                    "is_verified": True,
                },
            )
            if created:
                user.set_unusable_password()
                user.save()

            dp, _ = DemoProfile.objects.update_or_create(
                user=user,
                defaults={
                    "group_slug": data["group_slug"],
                    "trust_score": data["trust_score"],
                    "payout_position": data["payout_position"],
                    "is_current_winner": data.get("is_current_winner", False),
                    "monnify_account_number": (
                        data.get("monnify_account", {}).get("account_number", "")
                    ),
                    "monnify_bank_name": (
                        data.get("monnify_account", {}).get("bank_name", "")
                    ),
                    "monnify_account_name": (
                        data.get("monnify_account", {}).get("account_name", "")
                    ),
                    "offline_payin_code": data.get("offline_payin_code", ""),
                    "days_overdue": data.get("days_overdue", 0),
                    "kyc_verified": data.get("kyc_verified", False),
                    "bvn_match": data.get("bvn_match", ""),
                    "is_demo_user": True,
                },
            )
            users[data["id"]] = user
            self.stdout.write(f"  Created user: {data['name']}")
        return users

    def _create_demo_groups(self, users):
        groups = {}
        group_admin_map = {
            "techstars-01": users["usr-01"],
            "balogun-02": users["usr-06"],
        }
        for gdata in DEMO_GROUPS:
            admin = group_admin_map[gdata["slug"]]
            status_val = map_status(gdata["status"])

            group, _ = Group.objects.update_or_create(
                code=gdata["slug"],
                defaults={
                    "name": gdata["name"],
                    "admin": admin,
                    "contribution_amount": gdata["contribution_amount"],
                    "contribution_frequency": map_frequency(gdata["frequency"]),
                    "max_members": gdata["max_members"],
                    "status": status_val,
                    "current_round": gdata["current_round"],
                    "total_rounds": gdata["total_rounds"],
                },
            )
            groups[gdata["slug"]] = group
            self.stdout.write(f"  Created group: {gdata['name']}")
        return groups

    def _create_demo_memberships(self, users, groups):
        membership_map = {
            "techstars-01": [
                ("usr-01", "admin", 1),
                ("usr-02", "member", 2),
                ("usr-03", "member", 3),
                ("usr-04", "member", 4),
                ("usr-05", "member", 5),
            ],
            "balogun-02": [
                ("usr-06", "admin", 1),
                ("usr-07", "member", 2),
                ("usr-08", "member", 3),
                ("usr-09", "member", 4),
                ("usr-10", "member", 5),
            ],
        }
        for group_slug, members in membership_map.items():
            group = groups[group_slug]
            for uid, role, position in members:
                user = users[uid]
                Membership.objects.update_or_create(
                    user=user, group=group,
                    defaults={
                        "role": role,
                        "rotation_order": position,
                        "is_active": True,
                    },
                )

    def _create_demo_contributions(self, users, groups):
        contribution_map = {
            "techstars-01": {
                1: ["usr-01", "usr-02", "usr-03", "usr-04", "usr-05"],
                2: ["usr-01", "usr-02", "usr-03", "usr-04", "usr-05"],
                3: ["usr-01", "usr-02", "usr-03", "usr-04"],  # usr-05 unpaid
            },
            "balogun-02": {
                1: ["usr-06", "usr-07", "usr-08", "usr-09", "usr-10"],
                2: ["usr-06", "usr-07", "usr-09"],  # usr-08 overdue, usr-10 unpaid
            },
        }
        for group_slug, rounds in contribution_map.items():
            group = groups[group_slug]
            for round_num, paid_users in rounds.items():
                all_users_in_group = [
                    u for uid, u in users.items()
                    if DemoProfile.objects.filter(
                        user=u, group_slug=group_slug
                    ).exists()
                ]
                for user in all_users_in_group:
                    is_paid = user in [users[uid] for uid in paid_users]
                    status = "paid" if is_paid else "pending"

                    dp = DemoProfile.objects.get(user=user, group_slug=group_slug)
                    if dp.offline_payin_code and not is_paid and group_slug == "balogun-02":
                        status = "pending"
                    if dp.monnify_account_number and not is_paid and group_slug == "techstars-01":
                        status = "pending"

                    is_overdue = (
                        dp.days_overdue > 0 and
                        group_slug == "balogun-02" and
                        round_num == 2 and
                        not is_paid
                    )
                    if is_overdue:
                        status = "missed"

                    Contribution.objects.update_or_create(
                        user=user,
                        group=group,
                        round_number=round_num,
                        defaults={
                            "amount": group.contribution_amount,
                            "status": status,
                            "due_date": timezone.now().date() - timedelta(days=1),
                            "paid_at": (
                                timezone.now() - timedelta(days=1)
                                if is_paid else None
                            ),
                        },
                    )

    def _create_demo_wallets(self, users):
        for user in users.values():
            Wallet.objects.update_or_create(
                user=user,
                defaults={
                    "balance": 0.00,
                    "currency": "NGN",
                },
            )

    def _create_demo_payouts(self, users, groups):
        payout_rounds = {
            "techstars-01": {
                1: users["usr-01"],
                2: users["usr-02"],
            },
            "balogun-02": {
                1: users["usr-06"],
            },
        }
        for group_slug, rounds in payout_rounds.items():
            group = groups[group_slug]
            for round_num, recipient in rounds.items():
                payout_amount = group.contribution_amount * group.max_members
                Payout.objects.update_or_create(
                    group=group,
                    round_number=round_num,
                    defaults={
                        "recipient": recipient,
                        "amount": payout_amount,
                        "status": "paid",
                        "paid_at": timezone.now() - timedelta(days=2),
                    },
                )
                membership = Membership.objects.filter(
                    user=recipient, group=group
                ).first()
                if membership:
                    membership.has_received_payout = True
                    membership.save()
