from .models import Notification

def notify(user, type, title, message):
    """
    Helper to create notifications from anywhere in the app.

    Usage:
        from notifications.utils import notify
        notify(user, 'payment_due', 'Payment Due', 'Your contribution is due tomorrow.')
    """
    Notification.objects.create(
        user=user,
        type=type,
        title=title,
        message=message
    )


def notify_group(group, type, title, message, exclude_user=None):
    """Send a notification to all members of a group."""
    from groups.models import Membership
    members = Membership.objects.filter(
        group=group, is_active=True
    ).select_related('user')

    for membership in members:
        if exclude_user and membership.user == exclude_user:
            continue
        notify(membership.user, type, title, message)