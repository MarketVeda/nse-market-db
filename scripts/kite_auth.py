#!/usr/bin/env python3
"""
kite_auth.py - Fully automated Kite Connect login via pyotp
Fixed: Added totp_type parameter, clock tolerance, better error messages
"""

import sys, os, json, time, logging
import pyotp, requests
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from kiteconnect import KiteConnect

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

LOGIN_URL   = "https://kite.zerodha.com/api/login"
TWOFA_URL   = "https://kite.zerodha.com/api/twofa"
TOKEN_CACHE = "/tmp/kite_token.json"


def _load_cached_token(api_key):
    try:
        if not os.path.exists(TOKEN_CACHE):
            return None
        d = json.load(open(TOKEN_CACHE))
        if d.get("date") == datetime.today().strftime("%Y-%m-%d") and d.get("api_key") == api_key:
            return d.get("access_token")
    except Exception:
        pass
    return None


def _save_token(api_key, token):
    try:
        json.dump({"api_key": api_key, "access_token": token,
                   "date": datetime.today().strftime("%Y-%m-%d")},
                  open(TOKEN_CACHE, "w"))
    except Exception:
        pass


def _do_login(api_key, api_secret, user_id, password, totp_secret):
    sess = requests.Session()
    sess.headers.update({
        "User-Agent":     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Kite-Version": "3",
        "Content-Type":   "application/x-www-form-urlencoded",
    })

    # Step 1: Credentials
    log.info(f"[AUTH] Step 1: Login credentials for {user_id}")
    r1 = sess.post(LOGIN_URL, data={"user_id": user_id, "password": password})
    r1.raise_for_status()
    d1 = r1.json()
    if d1.get("status") != "success":
        raise RuntimeError(f"Step 1 failed: {d1.get('message', d1)}")
    request_id    = d1["data"]["request_id"]
    twofa_type    = d1["data"].get("twofa_type", "totp")   # get the type Kite expects
    log.info(f"[AUTH] Step 1 OK — request_id={request_id}, twofa_type={twofa_type}")

    # Step 2: TOTP — try current + adjacent time windows for clock tolerance
    log.info("[AUTH] Step 2: Generating TOTP")
    totp_obj = pyotp.TOTP(totp_secret)

    # Try current OTP first, then -1 and +1 windows if needed
    success = False
    for offset in [0, -1, 1, -2, 2]:
        otp = totp_obj.at(datetime.now(), counter_offset=offset)
        log.info(f"[AUTH] Trying TOTP offset={offset}: {otp}")
        r2 = sess.post(TWOFA_URL, data={
            "user_id":      user_id,
            "request_id":   request_id,
            "twofa_value":  otp,
            "twofa_type":   twofa_type,
            "skip_session": "",
        })
        if r2.status_code == 200:
            d2 = r2.json()
            if d2.get("status") == "success":
                log.info(f"[AUTH] Step 2 OK with offset={offset}")
                success = True
                break
            else:
                log.warning(f"[AUTH] TOTP offset={offset} rejected: {d2.get('message','')}")
        else:
            log.warning(f"[AUTH] TOTP offset={offset} HTTP {r2.status_code}: {r2.text[:200]}")
        time.sleep(0.5)

    if not success:
        raise RuntimeError(
            "Step 2 (TOTP) failed for all offsets.\n"
            "Possible causes:\n"
            "  1. Wrong TOTP secret — go to kite.zerodha.com → Profile → "
            "Password & Security → reset 2FA TOTP → click 'Can't scan? Copy key'\n"
            "  2. Zerodha account uses SMS OTP not TOTP — enable External TOTP first\n"
            "  3. Wrong KITE_USER_ID or KITE_PASSWORD"
        )

    # Step 3: Get request_token via connect/login redirect
    log.info("[AUTH] Step 3: Getting request_token via connect URL")
    connect_url = f"https://kite.trade/connect/login?v=3&api_key={api_key}"
    r3 = sess.get(connect_url, allow_redirects=True)
    final_url = r3.url
    log.info(f"[AUTH] Redirect final URL: {final_url}")

    parsed = urlparse(final_url)
    params = parse_qs(parsed.query)

    if "request_token" not in params:
        raise RuntimeError(
            f"request_token missing from redirect. Final URL: {final_url}\n"
            "FIX: Go to developers.kite.trade → your app → set Redirect URL to: https://127.0.0.1/"
        )

    request_token = params["request_token"][0]
    log.info(f"[AUTH] Step 3 OK — request_token={request_token[:12]}...")

    # Step 4: Generate access_token
    log.info("[AUTH] Step 4: Generating access_token")
    kite = KiteConnect(api_key=api_key)
    session_data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = session_data["access_token"]
    log.info(f"[AUTH] Step 4 OK — access_token obtained")
    return access_token


def get_kite():
    api_key     = os.environ["KITE_API_KEY"]
    api_secret  = os.environ["KITE_API_SECRET"]
    user_id     = os.environ["KITE_USER_ID"]
    password    = os.environ["KITE_PASSWORD"]
    totp_secret = os.environ["KITE_TOTP_SECRET"]

    kite = KiteConnect(api_key=api_key)

    # Try cached token
    cached = _load_cached_token(api_key)
    if cached:
        kite.set_access_token(cached)
        try:
            kite.profile()
            log.info("[AUTH] ✓ Using cached token")
            return kite
        except Exception:
            log.info("[AUTH] Cached token expired, re-logging in")

    # Full login with 3 retries
    for attempt in range(1, 4):
        try:
            token = _do_login(api_key, api_secret, user_id, password, totp_secret)
            kite.set_access_token(token)
            kite.profile()
            _save_token(api_key, token)
            log.info(f"[AUTH] ✓ Login successful on attempt {attempt}")
            return kite
        except RuntimeError as e:
            # RuntimeError means wrong credentials/config — don't retry
            log.error(f"[AUTH] Fatal error: {e}")
            raise
        except Exception as e:
            log.error(f"[AUTH] Attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(10)

    raise RuntimeError("All login attempts failed")
