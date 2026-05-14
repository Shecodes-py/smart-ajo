from django.contrib.auth import get_user_model

User = get_user_model()

# Scoring weights
MISSED_PENALTY = 30
LATE_PENALTY = 15
ONTIME_REWARD = 5

def calculate_risk_score(user):
    """
    Reads the user's full contribution history
    and returns a score between 0 and 100.
    0 = perfect, 100 = very high risk
    """
    contributions = user.contributions.all()
    total = contributions.count()

    if total == 0:
        return 0.0  # new user, no history yet

    missed = contributions.filter(status='missed').count()
    late = contributions.filter(status='late').count()
    ontime = contributions.filter(status='paid').count()

    raw_score = (missed * MISSED_PENALTY) + (late * LATE_PENALTY) - (ontime * ONTIME_REWARD)

    # clamp between 0 and 100
    score = max(0.0, min(100.0, raw_score))
    return round(score, 2)


def update_user_risk(user):
    """Recalculates and saves risk score + level for a user."""
    score = calculate_risk_score(user)

    user.risk_score = score
    user.total_contributions = user.contributions.count()
    user.missed_contributions = user.contributions.filter(status='missed').count()
    user.late_contributions = user.contributions.filter(status='late').count()

    if score < 30:
        user.risk_level = 'low'
    elif score < 70:
        user.risk_level = 'medium'
    else:
        user.risk_level = 'high'

    user.save()
    return user