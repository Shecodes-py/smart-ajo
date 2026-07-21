import os
import json
import requests
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class MonnifyClient:
    """
    Monnify API client for demo interactions.
    Falls back to mock responses when credentials are not configured.
    """

    def __init__(self):
        self.api_key = settings.MONNIFY_API_KEY
        self.secret_key = settings.MONNIFY_SECRET_KEY
        self.contract_code = settings.MONNIFY_CONTRACT_CODE
        self.base_url = settings.MONNIFY_BASE_URL
        self._token = None

    @property
    def _is_configured(self):
        return bool(self.api_key and self.secret_key and self.contract_code)

    def get_auth_token(self):
        if not self._is_configured:
            return {"success": True, "data": {"accessToken": "mock-token"}}
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                headers={"Content-Type": "application/json"},
                json={"apiKey": self.api_key, "secretKey": self.secret_key},
            )
            if resp.ok:
                data = resp.json()
                self._token = data.get("responseBody", {}).get("accessToken")
                return {"success": True, "data": data.get("responseBody", {})}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def create_reserved_account(self, account_name, account_reference, customer_email, customer_name):
        if not self._is_configured:
            return {
                "success": True,
                "data": {
                    "accountNumber": "7820193841",
                    "accountName": account_name,
                    "bankName": "Wema Bank",
                    "accountReference": account_reference,
                },
            }
        token_result = self.get_auth_token()
        if not token_result["success"]:
            return token_result
        try:
            resp = requests.post(
                f"{self.base_url}/api/v2/bank-transfer/reserved-accounts",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
                json={
                    "accountReference": account_reference,
                    "accountName": account_name,
                    "currencyCode": "NGN",
                    "contractCode": self.contract_code,
                    "customerEmail": customer_email,
                    "customerName": customer_name,
                    "getAllAvailableBanks": True,
                },
            )
            if resp.ok:
                return {"success": True, "data": resp.json().get("responseBody", {})}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def initiate_transfer(self, amount, destination_account_number, destination_bank_code, transaction_reference, narration="SmartAjo Demo Payout"):
        if not self._is_configured:
            return {
                "success": True,
                "data": {
                    "amount": amount,
                    "reference": transaction_reference,
                    "status": "SUCCESS",
                    "destinationAccountNumber": destination_account_number,
                    "destinationBankName": "Wema Bank",
                    "narration": narration,
                },
            }
        token_result = self.get_auth_token()
        if not token_result["success"]:
            return token_result
        try:
            resp = requests.post(
                f"{self.base_url}/api/v2/transactions/transfer",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._token}",
                },
                json={
                    "amount": amount,
                    "reference": transaction_reference,
                    "narration": narration,
                    "destinationBankCode": destination_bank_code,
                    "destinationAccountNumber": destination_account_number,
                    "currency": "NGN",
                    "sourceAccountNumber": None,
                },
            )
            if resp.ok:
                data = resp.json()
                return {"success": True, "data": data.get("responseBody", {})}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_account(self, account_number, bank_code):
        if not self._is_configured:
            return {
                "success": True,
                "data": {
                    "accountNumber": account_number,
                    "accountName": "SmartAjo Demo",
                    "bankName": "Wema Bank",
                },
            }
        token_result = self.get_auth_token()
        if not token_result["success"]:
            return token_result
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/disbursements/account/validate",
                params={
                    "accountNumber": account_number,
                    "bankCode": bank_code,
                },
                headers={
                    "Authorization": f"Bearer {self._token}",
                },
            )
            if resp.ok:
                return {"success": True, "data": resp.json().get("responseBody", {})}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def verify_payment(self, transaction_reference):
        if not self._is_configured:
            return {
                "success": True,
                "data": {
                    "transactionReference": transaction_reference,
                    "paymentStatus": "PAID",
                    "amount": 100000.00,
                },
            }
        token_result = self.get_auth_token()
        if not token_result["success"]:
            return token_result
        try:
            resp = requests.get(
                f"{self.base_url}/api/v2/transactions/{transaction_reference}",
                headers={
                    "Authorization": f"Bearer {self._token}",
                },
            )
            if resp.ok:
                return {"success": True, "data": resp.json().get("responseBody", {})}
            return {"success": False, "error": resp.text}
        except Exception as e:
            return {"success": False, "error": str(e)}


monnify_client = MonnifyClient()
