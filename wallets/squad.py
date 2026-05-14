import requests
import uuid
from django.conf import settings

SQUAD_BASE_URL = "https://sandbox-api-d.squadco.com"

HEADERS = {
    "Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}",
    "Content-Type": "application/json"
}

def generate_ref(prefix="AJO"):
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"

def initiate_funding(user, amount_naira):
    ref = generate_ref("FUND")
    payload = {
        "email": user.email,
        "amount": int(amount_naira * 100),
        "currency": "NGN",
        "initiate_type": "inline",
        "transaction_ref": ref,
        "customer_name": user.get_full_name(),
        "callback_url": settings.SQUAD_WALLET_CALLBACK_URL,
        "metadata": {
            "user_id": user.id,
            "type": "wallet_fund"
        }
    }
    response = requests.post(
        f"{SQUAD_BASE_URL}/transaction/initiate",
        json=payload,
        headers=HEADERS
    )
    data = response.json()
    if response.status_code == 200 and data.get("success"):
        return {
            "success": True,
            "checkout_url": data["data"]["checkout_url"],
            "transaction_ref": ref
        }
    return {"success": False, "error": data.get("message", "Failed to initiate funding.")}


def initiate_card_tokenization(user):
    """Charges ₦100 to tokenize card for future payments."""
    ref = generate_ref("CARD")
    payload = {
        "email": user.email,
        "amount": 10000,   # ₦100 in kobo
        "currency": "NGN",
        "initiate_type": "inline",
        "transaction_ref": ref,
        "customer_name": user.get_full_name(),
        "callback_url": settings.SQUAD_CARD_CALLBACK_URL,
        "metadata": {
            "user_id": user.id,
            "type": "card_tokenization"
        }
    }
    response = requests.post(
        f"{SQUAD_BASE_URL}/transaction/initiate",
        json=payload,
        headers=HEADERS
    )
    data = response.json()
    if response.status_code == 200 and data.get("success"):
        return {
            "success": True,
            "checkout_url": data["data"]["checkout_url"],
            "transaction_ref": ref
        }
    return {"success": False, "error": data.get("message", "Failed to initiate card tokenization.")}


def initiate_withdrawal(amount_naira, bank_code, account_number, account_name, ref):
    """Squad transfer to bank account."""
    payload = {
        "transaction_reference": ref,
        "amount": int(amount_naira * 100),
        "bank_code": bank_code,
        "account_number": account_number,
        "account_name": account_name,
        "currency_id": "NGN",
        "remark": "Smart Ajo Withdrawal"
    }
    response = requests.post(
        f"{SQUAD_BASE_URL}/payout/transfer",
        json=payload,
        headers=HEADERS
    )
    data = response.json()
    if response.status_code == 200 and data.get("success"):
        return {"success": True, "reference": ref}
    return {"success": False, "error": data.get("message", "Withdrawal failed.")}


def verify_transaction(transaction_ref):
    response = requests.get(
        f"{SQUAD_BASE_URL}/transaction/verify/{transaction_ref}",
        headers=HEADERS
    )
    data = response.json()
    if response.status_code == 200 and data.get("success"):
        return {
            "success": True,
            "status": data["data"]["transaction_status"],
            "amount": data["data"]["transaction_amount"] / 100,
            "metadata": data["data"].get("meta_data", {}),
            "card_token": data["data"].get("card_token"),
            "card": data["data"].get("card", {})
        }
    return {"success": False, "error": data.get("message", "Verification failed.")}