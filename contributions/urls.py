from django.urls import path
from .views import (
    InitiateContributionView, SquadCallbackView,
    GroupContributionsView, MyContributionsView,
    RoundSummaryView, GroupPayoutsView
)

# write your urls here
urlpatterns = [
    path('contribute/<int:group_id>/', InitiateContributionView.as_view(), name='contribute'),
    path('squad-callback/', SquadCallbackView.as_view(), name='squad-callback'),
    path('group/<int:group_id>/', GroupContributionsView.as_view(), name='group-contributions'),
    path('mine/', MyContributionsView.as_view(), name='my-contributions'),
    path('round-summary/<int:group_id>/', RoundSummaryView.as_view(), name='round-summary'),
    path('payouts/<int:group_id>/', GroupPayoutsView.as_view(), name='group-payouts'),
]