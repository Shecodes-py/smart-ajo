import base64
import requests
import json
import hashlib
import hmac
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class MonnifyClient:
    """
    Shared Monnify API client with token management.
    Handles authentication and provides base methods for all Monnify API calls.
    """

    def __init__(self):
        self.api_key = settings.MONNIFY_API_KEY
        self.secret_key = settings.MONNIFY_SECRET_KEY
        self.contract_code = settings.MONNIFY_CONTRACT_CODE
        self.base_url = settings.MONNIFY_BASE_URL
        self.wallet_account_number = getattr(settings, 'MONNIFY_WALLET_ACCOUNT_NUMBER', "")
        self._token = None

    @property
    def is_configured(self):
        return bool(self.api_key and self.secret_key and self.contract_code)

    def _get_basic_auth(self):
        credentials = f"{self.api_key}:{self.secret_key}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"

    def get_auth_token(self):
        if self._token:
            return {"success": True, "data": {"accessToken": self._token}}
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                headers={
                    "Authorization": self._get_basic_auth(),
                    "Content-Type": "application/json",
                },
            )
            if resp.ok:
                data = resp.json()
                if data.get("requestSuccessful"):
                    self._token = data["responseBody"]["accessToken"]
                    return {"success": True, "data": data["responseBody"]}
                return {"success": False, "error": data.get("responseMessage", "Auth failed")}
            return {"success": False, "error": f"Auth failed: {resp.status_code} {resp.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _headers(self):
        token_result = self.get_auth_token()
        if not token_result["success"]:
            raise Exception(f"Monnify auth failed: {token_result['error']}")
        return {
            "Authorization": f"Bearer {token_result['data']['accessToken']}",
            "Content-Type": "application/json",
        }

    def _post(self, endpoint, payload):
        try:
            resp = requests.post(
                f"{self.base_url}{endpoint}",
                json=payload,
                headers=self._headers(),
            )
            data = resp.json()
            if resp.ok and data.get("requestSuccessful"):
                return {"success": True, "data": data.get("responseBody", {}), "raw": data}
            return {"success": False, "error": data.get("responseMessage", f"HTTP {resp.status_code}"), "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get(self, endpoint, params=None):
        try:
            resp = requests.get(
                f"{self.base_url}{endpoint}",
                params=params,
                headers=self._headers(),
            )
            data = resp.json()
            if resp.ok and data.get("requestSuccessful"):
                return {"success": True, "data": data.get("responseBody", {}), "raw": data}
            return {"success": False, "error": data.get("responseMessage", f"HTTP {resp.status_code}"), "raw": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_payment_checkout(self, amount, customer_name, customer_email, payment_reference,
                                payment_description, redirect_url, payment_methods=None):
        payload = {
            "amount": float(amount),
            "customerName": customer_name,
            "customerEmail": customer_email,
            "paymentReference": payment_reference,
            "paymentDescription": payment_description,
            "currencyCode": "NGN",
            "contractCode": self.contract_code,
            "redirectUrl": redirect_url,
            "paymentMethods": payment_methods or ["CARD", "ACCOUNT_TRANSFER"],
        }
        return self._post("/api/v1/merchant/transactions/init-transaction", payload)

    def verify_transaction(self, transaction_reference):
        return self._get(f"/api/v2/transactions/{transaction_reference}")

    def single_transfer(self, amount, reference, destination_account_number,
                        destination_bank_code, destination_account_name, narration="SmartAjo transfer"):
        payload = {
            "amount": float(amount),
            "reference": reference,
            "narration": narration,
            "destinationBankCode": destination_bank_code,
            "destinationAccountNumber": destination_account_number,
            "destinationAccountName": destination_account_name,
            "currency": "NGN",
            "sourceAccountNumber": self.wallet_account_number,
        }
        return self._post("/api/v2/disbursements/single", payload)

    def reserve_account(self, account_reference, account_name, customer_email, customer_name):
        payload = {
            "accountReference": account_reference,
            "accountName": account_name,
            "currencyCode": "NGN",
            "contractCode": self.contract_code,
            "customerEmail": customer_email,
            "customerName": customer_name,
            "getAllAvailableBanks": True,
        }
        return self._post("/api/v2/bank-transfer/reserved-accounts", payload)

    def charge_card(self, amount, card_number, expiry_month, expiry_year, cvv, customer_email, customer_name, reference):
        payload = {
            "amount": float(amount),
            "cardNumber": card_number,
            "expiryMonth": expiry_month,
            "expiryYear": expiry_year,
            "cvv": cvv,
            "customerEmail": customer_email,
            "customerName": customer_name,
            "transactionReference": reference,
        }
        return self._post("/api/v1/merchant/cards/charge", payload)

    def verify_webhook_signature(self, request_body, signature_header):
        expected = hmac.new(
            self.secret_key.encode(),
            json.dumps(request_body, separators=(",", ":")).encode(),
            hashlib.sha512,
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header)


monnify = MonnifyClient()
