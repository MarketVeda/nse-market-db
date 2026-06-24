#!/usr/bin/env python3
"""
kite_auth.py
------------
Fully automated Kite Connect login using pyotp.
FIXED: Correct 3-step flow matching actual Kite Connect login sequence.

Flow:
  Step 1: POST user_id + password  → get request_id
  Step 2: POST request_id + TOTP   → session cookie set
  Step 3: GET kite.trade/connect/login?api_key=... → redirects to 127.0.0.1/?request_token=...
  Step 4: POST request_token + checksum → access_token

IMPORTANT: In your Kite Connect app at developers.kite.trade, set Redirect URL to:
  https://127.0.0.1/

Required env vars (GitHub Secrets):
  KITE_API_KEY, KITE_API_SECRET, KITE_USER_ID, KITE_PASSWORD, KITE_TOTP_SECRET
"""

import os
import sys
import json
import time
import logging
import pyotp
import requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

KITE_BASE   = "https://kite.zerodha.com"
LOGIN_URL   = f"{KITE_BASE}/api/login"
TWOFA_URL   = f"{KITE_BASE}/api/twofa"
TOKEN_CACHE = "/tmp/kite_token_cache.json"


def _load_cached_token(api_key: str):
    """Return cached access token if from today, else None."""
    try:
        if not os.path.exists(TOKEN_CACHE):
            return None
        with open(TOKEN_CACHE) as f:
            data = json.load(f)
        if (data.get("date") == datetime.today().strftime("%Y-%m-%d")
                and data.get("api_key") == api_key):
            log.info("Reusing cached access token from today")
            return data["access_token"]
    except Exception:
        pass
    return None


def _save_token(api_key: str, access_token: str):
    try:
        with open(TOKEN_CACHE, "w") as f:
            json.dump({
                "api_key":      api_key,
                "access_token": access_token,
                "date":         datetime.today().strftime("%Y-%m-%d"),
            }, f)
    except Exception as e:
        log.warning(f"Could not cache token: {e}")


def _do_login(api_key: str, api_secret: str,
              user_id: str, password: str, totp_secret: str) -> str:
    """Perform full automated Kite login. Returns access_token."""

    sess = requests.Session()
    sess.headers.update({
        "User-Agent":     "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "X-Kite-Version": "3",
    })

    # ── Step 1: POST credentials ──────────────────────────────────────────────
    log.info(f"[AUTH] Step 1: Posting credentials for {user_id}")
    r1 = sess.post(LOGIN_URL, data={"user_id": user_id, "password": password})
    r1.raise_for_status()
    d1 = r1.json()
    if d1.get("status") != "success":
        raise RuntimeError(f"Login failed: {d1.get('message', d1)}")
    request_id = d1["data"]["request_id"]
    log.info(f"[AUTH] Step 1 OK — request_id={request_id}")

    # ── Step 2: POST TOTP ─────────────────────────────────────────────────────
    log.info("[AUTH] Step 2: Submitting TOTP")
    otp = pyotp.TOTP(totp_secret).now()
    log.info(f"[AUTH] TOTP generated: {otp}")
    r2 = sess.post(TWOFA_URL, data={
        "user_id":      user_id,
        "request_id":   request_id,
        "twofa_value":  otp,
        "twofa_type":   "totp",
        "skip_session": "",
    })
    r2.raise_for_status()
    d2 = r2.json()
    if d2.get("status") != "success":
        raise RuntimeError(f"2FA failed: {d2.get('message', d2)}")
    log.info("[AUTH] Step 2 OK — 2FA accepted, session cookie set")

    # ── Step 3: GET connect/login with api_key → redirects with request_token ─
    log.info("[AUTH] Step 3: Getting request_token via connect/login redirect")
    connect_url = f"https://kite.trade/connect/login?v=3&api_key={api_key}"
    r3 = sess.get(connect_url, allow_redirects=True)
    # Final URL should be https://127.0.0.1/?request_token=XXX&action=login&status=success
    final_url = r3.url
    log.info(f"[AUTH] Redirect final URL: {final_url}")

    parsed = urlparse(final_url)
    params = parse_qs(parsed.query)

    if "request_token" not in params:
        raise RuntimeError(
            f"request_token not found in redirect URL: {final_url}\n"
            "FIX: Go to developers.kite.trade → your app → set Redirect URL "
            "to exactly: https://127.0.0.1/"
        )

    request_token = params["request_token"][0]
    log.info(f"[AUTH] Step 3 OK — request_token={request_token[:12]}...")

    # ── Step 4: Generate session → access_token ───────────────────────────────
    log.info("[AUTH] Step 4: Generating session / access_token")
    kite = KiteConnect(api_key=api_key)
    session_data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = session_data["access_token"]
    log.info(f"[AUTH] Step 4 OK — access_token={access_token[:12]}...")

    return access_token


def get_kite() -> KiteConnect:
    """
    Returns a fully authenticated KiteConnect instance.
    Automatically logs in using pyotp — no human needed.
    """
    api_key     = os.environ["KITE_API_KEY"]
    api_secret  = os.environ["KITE_API_SECRET"]
    user_id     = os.environ["KITE_USER_ID"]
    password    = os.environ["KITE_PASSWORD"]
    totp_secret = os.environ["KITE_TOTP_SECRET"]

    kite = KiteConnect(api_key=api_key)

    # Try cached token first
    token = _load_cached_token(api_key)
    if token:
        kite.set_access_token(token)
        try:
            kite.profile()
            log.info("[AUTH] ✓ Cached token valid")
            return kite
        except Exception:
            log.info("[AUTH] Cached token expired, re-logging in")

    # Full auto-login
    for attempt in range(1, 4):
        try:
            token = _do_login(api_key, api_secret, user_id, password, totp_secret)
            kite.set_access_token(token)
            kite.profile()          # validate
            _save_token(api_key, token)
            log.info("[AUTH] ✓ Login successful")
            return kite
        except Exception as e:
            log.error(f"[AUTH] Login attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(5)

    raise RuntimeError("All 3 login attempts failed. Check credentials and redirect URL.")
