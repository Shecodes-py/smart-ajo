import requests
import time
from django.conf import settings

SQUAD_BASE_URL = "https://sandbox-api-d.squadco.com"

HEADERS = {
    "Authorization": f"Bearer {settings.SQUAD_SECRET_KEY}",
    "Content-Type": "application/json"
}


def initiate_payment(user, group, amount_naira):
    """
    Initializes a Squad payment transaction.
    Returns the checkout URL the user visits to pay.
    """
    
    customer_name = user.get_full_name().strip() or user.username or user.email
    tx_ref = f"AJO-{user.id}-{group.id}-{group.current_round}-{int(time.time())}"

    payload = {
        "email": user.email,
        "amount": int(amount_naira * 100),  # Squad uses kobo
        "currency": "NGN",
        "initiate_type": "inline",
        "transaction_ref": tx_ref,
        "customer_name": customer_name,
        "callback_url": settings.SQUAD_CALLBACK_URL,
        # "redirect_url": f"{settings.SQUAD_REDIRECT_URL.rstrip('/')}/pages/payment-success.html",

        "meta_data": {
            "user_id": user.id,
            "group_id": group.id,
            "round_number": group.current_round
        }
    }

    response = requests.post(
        f"{SQUAD_BASE_URL}/transaction/initiate",
        json=payload,
        headers=HEADERS
    )

    data = response.json()

    if response.status_code == 200 and data.get('success'):
        return {
            "success": True,
            "checkout_url": data['data']['checkout_url'],
            "transaction_ref": payload['transaction_ref']
        }

    return {
        "success": False,
        "error": data.get('message', 'Payment initiation failed.')
    }


def verify_payment(transaction_ref):
    """
    Verifies a payment after Squad redirects back to your callback URL.
    Call this inside your webhook/callback view.
    """
    response = requests.get(
        f"{SQUAD_BASE_URL}/transaction/verify/{transaction_ref}",
        headers=HEADERS
    )

    data = response.json()

    if response.status_code == 200 and data.get('success'):
        transaction = data['data']
        return {
            "success": True,
            "status": transaction['transaction_status'],  # success or failed
            "amount": transaction['transaction_amount'] / 100,  # convert back to naira
            "ref": transaction['transaction_ref'],
            "metadata": transaction.get('meta_data', {})
        }

    return {
        "success": False,
        "error": data.get('message', 'Verification failed.')
    }