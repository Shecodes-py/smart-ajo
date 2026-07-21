import uuid
from django.conf import settings
from smartajo.monnify_client import monnify


def generate_ref(prefix="AJO"):
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


def initiate_funding(user, amount_naira):
    ref = generate_ref("FUND")
    customer_name = user.get_full_name().strip() or user.username or user.email
    redirect_url = f"{settings.MONNIFY_CALLBACK_BASE_URL}/api/wallet/fund/callback/"

    result = monnify.create_payment_checkout(
        amount=amount_naira,
        customer_name=customer_name,
        customer_email=user.email,
        payment_reference=ref,
        payment_description=f"Wallet funding — SmartAjo",
        redirect_url=redirect_url,
    )

    if result["success"]:
        return {
            "success": True,
            "checkout_url": result["data"].get("checkoutUrl", ""),
            "transaction_ref": result["data"].get("transactionReference", ref),
        }

    return {
        "success": False,
        "error": result.get("error", "Failed to initiate funding."),
    }


def initiate_card_tokenization(user):
    customer_name = user.get_full_name().strip() or user.username or user.email
    ref = generate_ref("CARD")
    redirect_url = f"{settings.MONNIFY_CALLBACK_BASE_URL}/api/payments/card/callback/"

    result = monnify.create_payment_checkout(
        amount=100.00,
        customer_name=customer_name,
        customer_email=user.email,
        payment_reference=ref,
        payment_description="Card tokenization — SmartAjo",
        redirect_url=redirect_url,
    )

    if result["success"]:
        return {
            "success": True,
            "checkout_url": result["data"].get("checkoutUrl", ""),
            "transaction_ref": result["data"].get("transactionReference", ref),
        }

    return {
        "success": False,
        "error": result.get("error", "Failed to initiate card tokenization."),
    }


def initiate_withdrawal(amount_naira, bank_code, account_number, account_name, ref):
    result = monnify.single_transfer(
        amount=amount_naira,
        reference=ref,
        destination_account_number=account_number,
        destination_bank_code=bank_code,
        destination_account_name=account_name,
        narration="SmartAjo withdrawal",
    )

    if result["success"]:
        return {
            "success": True,
            "reference": ref,
            "status": result["data"].get("status", "PENDING"),
        }

    return {
        "success": False,
        "error": result.get("error", "Withdrawal failed."),
    }


def verify_transaction(transaction_reference):
    result = monnify.verify_transaction(transaction_reference)

    if result["success"]:
        data = result["data"]
        payment_status = data.get("paymentStatus", "").upper()
        is_success = payment_status == "PAID"

        return {
            "success": True,
            "status": "success" if is_success else payment_status.lower(),
            "amount": data.get("amountPaid", 0),
            "metadata": {
                "user_id": None,
                "type": None,
            },
            "card_token": None,
            "card": {},
        }

    return {
        "success": False,
        "error": result.get("error", "Verification failed."),
    }
