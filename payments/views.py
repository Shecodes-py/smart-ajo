from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import SavedCard
from .serializers import SavedCardSerializer
from wallets.squad import initiate_card_tokenization, verify_transaction

# Create your views here.
class AddCardView(APIView):
    """POST /api/payments/add-card/ — initiates ₦100 charge to tokenize card"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = initiate_card_tokenization(request.user)

        if not result["success"]:
            return Response(
                {"error": result["error"]},
                status=status.HTTP_502_BAD_GATEWAY
            )

        return Response({
            "checkout_url": result["checkout_url"],
            "transaction_ref": result["transaction_ref"],
            "message": "Complete payment to save your card."
        }, status=status.HTTP_200_OK)


class CardCallbackView(APIView):
    """POST /api/payments/card/callback/ — Squad webhook after tokenization"""
    permission_classes = []

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

        metadata = result.get("metadata", {})
        user_id = metadata.get("user_id")
        card_data = result.get("card", {})
        card_token = result.get("card_token")

        if not card_token or not user_id:
            return Response({"error": "Missing card token or user."}, status=400)

        from django.contrib.auth import get_user_model
        User = get_user_model()

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found."}, status=404)

        # Save the card
        SavedCard.objects.get_or_create(
            user=user,
            token=card_token,
            defaults={
                "last4": card_data.get("last4", "****"),
                "brand": card_data.get("card_type", "Unknown"),
                "exp_month": card_data.get("expiry_month", ""),
                "exp_year": card_data.get("expiry_year", ""),
            }
        )

        return Response({"message": "Card saved successfully."}, status=200)


class ListCardsView(APIView):
    """GET /api/payments/cards/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cards = SavedCard.objects.filter(user=request.user)
        serializer = SavedCardSerializer(cards, many=True)
        return Response(serializer.data)


class DeleteCardView(APIView):
    """DELETE /api/payments/cards/{id}/"""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        card = get_object_or_404(SavedCard, pk=pk, user=request.user)
        card.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)