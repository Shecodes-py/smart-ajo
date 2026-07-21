import time
import uuid
from django.conf import settings
from smartajo.monnify_client import monnify


def initiate_payment(user, group, amount_naira):
    customer_name = user.get_full_name().strip() or user.username or user.email
    payment_ref = f"AJO-{user.id}-{group.id}-{group.current_round}-{int(time.time())}"
    redirect_url = f"{settings.MONNIFY_CALLBACK_BASE_URL}/api/contributions/monnify-callback/"

    result = monnify.create_payment_checkout(
        amount=amount_naira,
        customer_name=customer_name,
        customer_email=user.email,
        payment_reference=payment_ref,
        payment_description=f"Contribution to {group.name} — Round {group.current_round}",
        redirect_url=redirect_url,
    )

    if result["success"]:
        return {
            "success": True,
            "checkout_url": result["data"].get("checkoutUrl", ""),
            "transaction_ref": result["data"].get("transactionReference", payment_ref),
            "payment_reference": payment_ref,
        }

    return {
        "success": False,
        "error": result.get("error", "Payment initiation failed."),
    }


def verify_payment(transaction_reference):
    result = monnify.verify_transaction(transaction_reference)

    if result["success"]:
        data = result["data"]
        payment_status = data.get("paymentStatus", "").upper()

        is_success = payment_status == "PAID"

        return {
            "success": True,
            "status": "success" if is_success else payment_status.lower(),
            "amount": data.get("amountPaid", 0),
            "ref": data.get("transactionReference", ""),
            "payment_reference": data.get("paymentReference", ""),
            "customer": data.get("customer", {}),
            "paid_on": data.get("paidOn"),
        }

    return {
        "success": False,
        "error": result.get("error", "Verification failed."),
    }


def parse_transaction_ref(payment_reference):
    try:
        parts = payment_reference.split("-")
        if len(parts) >= 4 and parts[0] == "AJO":
            return {
                "user_id": int(parts[1]),
                "group_id": int(parts[2]),
                "round_number": int(parts[3]),
            }
        return None
    except (ValueError, IndexError):
        return None
