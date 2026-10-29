"""
OTP codes, SMS delivery and signed session tokens.

    send  → random 6-digit code, HMAC stored in auth.otp_challenges, SMS sent
    verify → constant-time compare, attempt counter, 5-minute expiry
    token → "<payload>.<hmac>" carrying the phone and guest_id, valid 7 days

SMS providers (env YUP_SMS_PROVIDER):
    console   (default) prints the code in the server log; with YUP_OTP_DEMO=1
              the API also returns it, so a demo works without an SMS account
    fast2sms  India — needs FAST2SMS_API_KEY (OTP route)
    twilio    worldwide — needs TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import urllib.parse
import urllib.request
from pathlib import Path

from fastapi import Header, HTTPException

log = logging.getLogger("yup.auth")

OTP_TTL_SECONDS = 300
OTP_MAX_ATTEMPTS = 5
SEND_LIMIT, SEND_WINDOW_MIN, RESEND_COOLDOWN_S = 3, 10, 30
TOKEN_TTL_SECONDS = 7 * 24 * 3600


def _load_secret() -> bytes:
    """YUP_SECRET in production; locally a random secret kept in ~/.yupreserved/secret."""
    if os.getenv("YUP_SECRET"):
        return os.environ["YUP_SECRET"].encode()
    path = Path.home() / ".yupreserved" / "secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(secrets.token_hex(32))
        path.chmod(0o600)
    return path.read_text().strip().encode()


SECRET = _load_secret()
SMS_PROVIDER = os.getenv("YUP_SMS_PROVIDER", "console").lower()
OTP_DEMO = os.getenv("YUP_OTP_DEMO", "1" if SMS_PROVIDER == "console" else "0") == "1"
WEBOTP_HOST = os.getenv("YUP_PUBLIC_HOST", "")          # e.g. yupreserved.onrender.com, for SMS autofill


# ── OTP ────────────────────────────────────────────────────────────────────
def new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def code_hash(phone: str, code: str) -> str:
    return hmac.new(SECRET, f"{phone}:{code}".encode(), hashlib.sha256).hexdigest()


def codes_match(stored_hash: str, phone: str, code: str) -> bool:
    return hmac.compare_digest(stored_hash, code_hash(phone, code))


def send_sms(phone: str, code: str) -> None:
    text = f"{code} is your YupReserved code. It expires in 5 minutes. Never share it."
    if WEBOTP_HOST:
        text += f"\n\n@{WEBOTP_HOST} #{code}"            # lets Android Chrome fill the code in automatically
    if SMS_PROVIDER == "console":
        log.warning("OTP for +91 %s: %s (console provider — no SMS sent)", phone, code)
        return
    if SMS_PROVIDER == "fast2sms":
        body = urllib.parse.urlencode({"route": "otp", "variables_values": code, "numbers": phone}).encode()
        req = urllib.request.Request("https://www.fast2sms.com/dev/bulkV2", data=body,
                                     headers={"authorization": os.environ["FAST2SMS_API_KEY"]})
    elif SMS_PROVIDER == "twilio":
        sid = os.environ["TWILIO_ACCOUNT_SID"]
        auth = base64.b64encode(f"{sid}:{os.environ['TWILIO_AUTH_TOKEN']}".encode()).decode()
        body = urllib.parse.urlencode({"To": f"+91{phone}", "From": os.environ["TWILIO_FROM"], "Body": text}).encode()
        req = urllib.request.Request(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=body,
                                     headers={"Authorization": f"Basic {auth}"})
    else:
        raise RuntimeError(f"unknown YUP_SMS_PROVIDER {SMS_PROVIDER!r}")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            r.read()
    except Exception as e:                                   # never leak provider details to the user
        log.error("SMS provider %s failed: %s", SMS_PROVIDER, e)
        raise HTTPException(502, "We couldn't send the SMS right now. Please try again in a minute.")


# ── session tokens ─────────────────────────────────────────────────────────
def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def issue_token(phone: str, guest_id: int | None) -> str:
    payload = _b64(json.dumps({"phone": phone, "guest_id": guest_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}).encode())
    sig = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{sig}"


def read_token(token: str) -> dict:
    try:
        payload, sig = token.split(".")
        good = _b64(hmac.new(SECRET, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, good):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if data["exp"] < time.time():
            raise ValueError
        return data
    except Exception:
        raise HTTPException(401, "Your session has expired. Please sign in again.")


def session(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: the signed-in phone (and guest_id, if the account exists)."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Please sign in with your mobile number first.")
    return read_token(authorization.removeprefix("Bearer ").strip())


def require_guest(s: dict, guest_id: int | None = None) -> int:
    if not s.get("guest_id"):
        raise HTTPException(403, "Finish creating your account first.")
    if guest_id is not None and guest_id != s["guest_id"]:
        raise HTTPException(403, "That belongs to another guest.")
    return s["guest_id"]
