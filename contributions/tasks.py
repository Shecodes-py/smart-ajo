from celery import shared_task
from django.utils import timezone
from django.contrib.auth import get_user_model

from groups.models import Group, Membership
from .models import Contribution
from .risks import update_user_risk
from notifications.utils import notify

from time import timedelta

User = get_user_model()

@shared_task
def mark_missed_contributions():
    """
    Runs every day at midnight Lagos time.
    Finds all pending contributions whose due date has passed
    and marks them as missed, then updates risk scores.
    """
    today = timezone.now().date()

    GRACE_DAYS = {
        'daily': 0,      # no grace — mark missed same day at midnight
        'weekly': 2,
        'biweekly': 3,
        'monthly': 7,
    }


    # Find all pending contributions that are overdue
    overdue = Contribution.objects.filter(
        status='pending',
        due_date__lt=today
    )

    missed_count = 0
    affected_users = set()

    for contribution in overdue:
        freq = contribution.group.frequency or 'monthly'
        grace = GRACE_DAYS.get(freq, 0)
        deadline = contribution.due_date + timedelta(days=grace)
        
        if today > deadline:
            contribution.status = 'missed'
            contribution.save()
            affected_users.add(contribution.user_id)
            missed_count += 1
        elif today >= contribution.due_date:
            # Within grace period — mark late but not missed
            contribution.status = 'late'
            contribution.save()
            affected_users.add(contribution.user_id)


        notify(
                contribution.user,
                'missed_payment',
                '⚠️ Missed Contribution',
                f'You missed your contribution for {contribution.group.name} Round {contribution.round_number}. This affects your risk score.'
            )

        affected_users.add(contribution.user_id)
        missed_count += 1

    # Recalculate risk score for every affected user
    for user_id in affected_users:
        try:
            user = User.objects.get(id=user_id)
            update_user_risk(user)
        except User.DoesNotExist:
            pass

    return f"{missed_count} contributions marked as missed. {len(affected_users)} users risk scores updated."


@shared_task
def create_round_contributions():
    """
    Runs at the start of each round based on group frequency.
    Creates pending contribution records for every member
    so they know they have a payment due.
    """
    today = timezone.now().date()
    active_groups = Group.objects.filter(status='active')

    created_count = 0

    for group in active_groups:
        due_date = calculate_due_date(group, today)
        members = Membership.objects.filter(group=group, is_active=True)

        for membership in members:
            contribution, created = Contribution.objects.get_or_create(
                user=membership.user,
                group=group,
                round_number=group.current_round,
                defaults={
                    'amount': group.contribution_amount,
                    'status': 'pending',
                    'due_date': due_date
                }
            )
            if created:
                created_count += 1

    return f"{created_count} contribution records created."


@shared_task
def send_payment_reminders():
    """
    Runs every day.
    Sends email reminders to members who haven't paid yet
    and their due date is tomorrow.
    """
    from django.core.mail import send_mail
    from django.conf import settings

    tomorrow = timezone.now().date() + timezone.timedelta(days=1)

    pending = Contribution.objects.filter(
        status='pending',
        due_date=tomorrow
    ).select_related('user', 'group')

    reminded_count = 0

    for contribution in pending:
        try:
            send_mail(
                subject=f"⏰ Payment Reminder — {contribution.group.name}",
                message=(
                    f"Hi {contribution.user.get_full_name()},\n\n"
                    f"Your contribution of ₦{contribution.amount} for "
                    f"{contribution.group.name} (Round {contribution.round_number}) "
                    f"is due tomorrow.\n\n"
                    f"Please log in to Smart Ajo and make your payment to avoid "
                    f"being marked as missed and affecting your risk score.\n\n"
                    f"Smart Ajo Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[contribution.user.email],
                fail_silently=True
            )
            reminded_count += 1

            notify(
                    contribution.user,
                    'payment_due',
                    'Payment Due Tomorrow',
                    f'Your ₦{contribution.amount:,.0f} contribution to {contribution.group.name} is due tomorrow.'
                )
        except Exception:
            pass

    return f"Reminders sent to {reminded_count} members."


def calculate_due_date(group, from_date):
    """Calculate due date based on group frequency."""
    from datetime import timedelta

    frequency_days = {
        'daily': 1,
        'weekly': 7,
        'biweekly': 14,
        'monthly': 30
    }

    days = frequency_days.get(group.frequency, 7)
    return from_date + timedelta(days=days)