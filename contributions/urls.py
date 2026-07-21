from django.urls import path
from .views import (
    InitiateContributionView, MonnifyCallbackView,
    GroupContributionsView, MyContributionsView,
    RoundSummaryView, GroupPayoutsView, SeedContributionView
)

# write your urls here
urlpatterns = [
    path('contribute/<int:group_id>/', InitiateContributionView.as_view(), name='contribute'),
    path('monnify-callback/', MonnifyCallbackView.as_view(), name='monnify-callback'),
    path('group/<int:group_id>/', GroupContributionsView.as_view(), name='group-contributions'),
    path('mine/', MyContributionsView.as_view(), name='my-contributions'),
    path('round-summary/<int:group_id>/', RoundSummaryView.as_view(), name='round-summary'),
    path('payouts/<int:group_id>/', GroupPayoutsView.as_view(), name='group-payouts'),

    path('seed/', SeedContributionView.as_view(), name='seed-contribution'),  
]