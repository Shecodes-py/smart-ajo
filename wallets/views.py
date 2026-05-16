from django.shortcuts import redirect
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status, generics
from django.conf import settings

from .models import Wallet, WalletTransaction
from .squad import initiate_funding, initiate_withdrawal, verify_transaction, generate_ref
from .serializers import WalletSerializer, WalletTransactionSerializer

# Create your views here.
class WalletView(APIView):
    """GET /api/wallet/ — returns balance"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        return Response({
            "balance": wallet.balance,
            "currency": wallet.currency
        })


class FundWalletView(APIView):
    """POST /api/wallet/fund/ — initiates Squad payment to top up wallet"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount")

        if not amount or float(amount) < 100:
            return Response(
                {"error": "Minimum funding amount is ₦100."},
                status=status.HTTP_400_BAD_REQUEST
            )

        result = initiate_funding(request.user, float(amount))

        if not result["success"]:
            return Response(
                {"error": result["error"]},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Create a pending transaction record
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        WalletTransaction.objects.create(
            wallet=wallet,
            type="fund",
            amount=amount,
            status="pending",
            reference=result["transaction_ref"],
            description="Wallet funding via Squad"
        )

        return Response({
            "checkout_url": result["checkout_url"],
            "transaction_ref": result["transaction_ref"]
        }, status=status.HTTP_200_OK)


class WalletFundCallbackView(APIView):
    """POST /api/wallet/fund/callback/ — Squad webhook after funding"""
    permission_classes = []

    def get(self, request):
        """Browser redirect after Squad checkout."""
        transaction_ref = request.query_params.get('reference') or \
                          request.query_params.get('transaction_ref')

        if not transaction_ref:
            return redirect(f"{settings.FRONTEND_URL}/pages/wallet.html?status=failed")

        result = verify_transaction(transaction_ref)

        if not result['success'] or result['status'] != 'success':
            return redirect(f"{settings.FRONTEND_URL}/pages/wallet.html?status=failed")

        try:
            txn = WalletTransaction.objects.get(reference=transaction_ref)
            if txn.status != 'success':
                txn.status = 'success'
                txn.save()
                wallet = txn.wallet
                wallet.balance += txn.amount
                wallet.save()
        except WalletTransaction.DoesNotExist:
            return redirect(f"{settings.FRONTEND_URL}/pages/wallet.html?status=failed")

        return redirect(f"{settings.FRONTEND_URL}/pages/wallet.html?status=success")


    def post(self, request):
        transaction_ref = (
            request.data.get("transaction_ref") or
            request.query_params.get("transaction_ref")
        )

        if not transaction_ref:
            return Response({"error": "No transaction ref."}, status=400)

        result = verify_transaction(transaction_ref)
        if not result["success"] or result["status"] != "success":
            return Response({"message": "Payment not successful."}, status=200)

        try:
            txn = WalletTransaction.objects.get(reference=transaction_ref)
            if txn.status == "success":
                return Response({"message": "Already processed."}, status=200)

            # Credit the wallet
            txn.status = "success"
            txn.save()

            wallet = txn.wallet
            wallet.balance += txn.amount
            wallet.save()

            return Response({"message": "Wallet funded successfully."}, status=200)

        except WalletTransaction.DoesNotExist:
            return Response({"error": "Transaction not found."}, status=404)


class WithdrawView(APIView):
    """POST /api/wallet/withdraw/"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get("amount")
        bank_code = request.data.get("bank_code")
        account_number = request.data.get("account_number")
        account_name = request.data.get("account_name", request.user.get_full_name())

        if not all([amount, bank_code, account_number]):
            return Response(
                {"error": "amount, bank_code, and account_number are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        amount = float(amount)
        wallet, _ = Wallet.objects.get_or_create(user=request.user)

        if not wallet.can_withdraw(amount):
            return Response(
                {"error": f"Insufficient balance. Your balance is ₦{wallet.balance}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        ref = generate_ref("WDRAW")
        result = initiate_withdrawal(amount, bank_code, account_number, account_name, ref)

        if not result["success"]:
            return Response(
                {"error": result["error"]},
                status=status.HTTP_502_BAD_GATEWAY
            )

        # Deduct balance and record transaction
        wallet.balance -= amount
        wallet.save()

        WalletTransaction.objects.create(
            wallet=wallet,
            type="withdrawal",
            amount=amount,
            status="success",
            reference=ref,
            description=f"Withdrawal to {account_number} ({bank_code})"
        )

        return Response({
            "message": f"₦{amount:,.2f} withdrawal initiated successfully.",
            "reference": ref
        }, status=status.HTTP_200_OK)


class WalletTransactionsView(generics.ListAPIView):
    """GET /api/wallet/transactions/"""
    permission_classes = [IsAuthenticated]
    serializer_class = WalletTransactionSerializer

    def get_queryset(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet.transactions.all()