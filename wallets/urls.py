from django.urls import path
from .views import (
    WalletView, FundWalletView, WalletFundCallbackView,
    WithdrawView, WalletTransactionsView
)

urlpatterns = [
    path('', WalletView.as_view(), name='wallet'),
    path('fund/', FundWalletView.as_view(), name='fund-wallet'),
    path('fund/callback/', WalletFundCallbackView.as_view(), name='fund-callback'),
    path('withdraw/', WithdrawView.as_view(), name='withdraw'),
    path('transactions/', WalletTransactionsView.as_view(), name='wallet-transactions'),
]