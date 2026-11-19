"""Minimal Razorpay REST client and signature helpers (server-side only).

Uses httpx against https://api.razorpay.com/v1 so no extra SDK is needed.
Tests patch create_order and fetch_payment; nothing here is called for real in tests.
"""
import hashlib
import hmac
from typing import Any, Dict

import httpx

from app.core.config import settings

API_BASE = "https://api.razorpay.com/v1"


class RazorpayError(Exception):
    """Razorpay API or configuration failure (message is safe to log, never includes secrets)."""


def _secret(value) -> str:
    return value.get_secret_value() if value else ""


def is_configured() -> bool:
    return bool(settings.RAZORPAY_KEY_ID and _secret(settings.RAZORPAY_KEY_SECRET))


def _request(method: str, path: str, **kwargs) -> Dict[str, Any]:
    if not is_configured():
        raise RazorpayError("Razorpay is not configured")
    auth = (settings.RAZORPAY_KEY_ID, _secret(settings.RAZORPAY_KEY_SECRET))
    try:
        with httpx.Client(timeout=15.0, auth=auth) as client:
            response = client.request(method, f"{API_BASE}{path}", **kwargs)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as error:
        raise RazorpayError(f"Razorpay request failed ({type(error).__name__})") from None


def create_order(amount: int, currency: str, receipt: str, notes: Dict[str, str]) -> Dict[str, Any]:
    return _request("POST", "/orders", json={"amount": amount, "currency": currency,
                                              "receipt": receipt, "notes": notes})


def fetch_payment(payment_id: str) -> Dict[str, Any]:
    return _request("GET", f"/payments/{payment_id}")


def checkout_signature_valid(order_id: str, payment_id: str, signature: str) -> bool:
    """Standard Checkout signature: HMAC-SHA256 of order_id|payment_id with the key secret."""
    secret = _secret(settings.RAZORPAY_KEY_SECRET)
    if not secret:
        return False
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")


def webhook_signature_valid(raw_body: bytes, signature: str) -> bool:
    """Webhook signature: HMAC-SHA256 of the raw body with the webhook secret."""
    secret = _secret(settings.RAZORPAY_WEBHOOK_SECRET)
    if not secret:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
