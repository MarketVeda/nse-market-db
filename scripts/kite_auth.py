#!/usr/bin/env python3
"""
kite_auth.py - Fully automated Kite Connect login via pyotp
Fixed: Capture request_token from redirect without actually connecting to 127.0.0.1
The trick: disable allow_redirects and read the Location header directly.
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
            log.info("[AUTH] Found cached token for today")
            return d.get("access_token")
    except Exception:
        pass
    return None


def _save_token(api_key, token):
    try:
        json.dump({"api_key": api_key, "access_token": token,
                   "date": datetime.today().strftime("%Y-%m-%d")},
                  open(TOKEN_CACHE, "w"))
    except Exception as e:
        log.warning(f"[AUTH] Could not cache token: {e}")


def _extract_request_token(sess, api_key):
    """
    Get request_token by following the Kite connect/login redirect chain
    WITHOUT actually connecting to 127.0.0.1.
    We intercept the redirect at the last hop and read the Location header.
    """
    connect_url = f"https://kite.trade/connect/login?v=3&api_key={api_key}"
    log.info(f"[AUTH] Step 3: GET {connect_url}")

    # Follow redirects manually, stop before connecting to 127.0.0.1
    url = connect_url
    for hop in range(10):
        try:
            resp = sess.get(url, allow_redirects=False, timeout=15)
        except requests.exceptions.ConnectionError as e:
            # If we already hit 127.0.0.1 connection error, the URL is in the exception
            err_str = str(e)
            log.info(f"[AUTH] Connection error on hop {hop}: {err_str[:200]}")
            # Try to extract URL from error message
            if "127.0.0.1" in err_str:
                # Extract from the pool URL in error
                import re
                match = re.search(r"url: ([^\s]+)", err_str)
                if match:
                    redirect_url = "http://127.0.0.1/" + match.group(1).split("/", 3)[-1] if "/" in match.group(1) else match.group(1)
                    log.info(f"[AUTH] Extracted URL from error: {redirect_url}")
                    parsed = urlparse(redirect_url)
                    params = parse_qs(parsed.query)
                    if "request_token" in params:
                        return params["request_token"][0]
            raise

        location = resp.headers.get("Location", "")
        log.info(f"[AUTH] Hop {hop}: status={resp.status_code}, Location={location[:100]}")

        if resp.status_code in (301, 302, 303, 307, 308) and location:
            # Check if this redirect points to our redirect URL (127.0.0.1)
            if "127.0.0.1" in location or "request_token" in location:
                log.info(f"[AUTH] Found redirect to callback: {location[:200]}")
                parsed = urlparse(location)
                params = parse_qs(parsed.query)
                if "request_token" in params:
                    return params["request_token"][0]
                # request_token might be in fragment
                if "request_token" in parsed.fragment:
                    frag_params = parse_qs(parsed.fragment)
                    if "request_token" in frag_params:
                        return frag_params["request_token"][0]
            url = location
            continue

        # Non-redirect response — check if request_token is in final URL
        parsed = urlparse(resp.url)
        params = parse_qs(parsed.query)
        if "request_token" in params:
            return params["request_token"][0]

        log.warning(f"[AUTH] Unexpected response on hop {hop}: status={resp.status_code}")
        break

    raise RuntimeError(
        "Could not extract request_token from redirect chain.\n"
        "Make sure Redirect URL in developers.kite.trade is set to: https://127.0.0.1/"
    )


def _do_login(api_key, api_secret, user_id, password, totp_secret):
    sess = requests.Session()
    sess.headers.update({
        "User-Agent":     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "X-Kite-Version": "3",
        "Content-Type":   "application/x-www-form-urlencoded",
    })

    # Step 1: POST credentials
    log.info(f"[AUTH] Step 1: Posting credentials for {user_id}")
    r1 = sess.post(LOGIN_URL, data={"user_id": user_id, "password": password})
    r1.raise_for_status()
    d1 = r1.json()
    if d1.get("status") != "success":
        raise RuntimeError(f"Step 1 failed: {d1.get('message', d1)}")
    request_id = d1["data"]["request_id"]
    twofa_type = d1["data"].get("twofa_type", "totp")
    log.info(f"[AUTH] Step 1 OK — request_id={request_id}, twofa_type={twofa_type}")

    # Step 2: POST TOTP with clock tolerance
    log.info("[AUTH] Step 2: Generating and submitting TOTP")
    totp_obj = pyotp.TOTP(totp_secret)
    success  = False
    for offset in [0, -1, 1, -2, 2]:
        otp = totp_obj.at(datetime.now(), counter_offset=offset)
        log.info(f"[AUTH] TOTP offset={offset}: {otp}")
        r2 = sess.post(TWOFA_URL, data={
            "user_id":      user_id,
            "request_id":   request_id,
            "twofa_value":  otp,
            "twofa_type":   twofa_type,
            "skip_session": "",
        })
        if r2.status_code == 200 and r2.json().get("status") == "success":
            log.info(f"[AUTH] Step 2 OK with offset={offset}")
            success = True
            break
        log.warning(f"[AUTH] offset={offset} rejected: {r2.status_code} {r2.text[:100]}")
        time.sleep(0.5)

    if not success:
        raise RuntimeError(
            "TOTP rejected. Ensure KITE_TOTP_SECRET matches the key shown when "
            "you enabled External TOTP on kite.zerodha.com"
        )

    # Step 3: Get request_token from redirect
    request_token = _extract_request_token(sess, api_key)
    log.info(f"[AUTH] Step 3 OK — request_token={request_token[:12]}...")

    # Step 4: Generate access_token
    log.info("[AUTH] Step 4: Generating access_token")
    kite = KiteConnect(api_key=api_key)
    data = kite.generate_session(request_token, api_secret=api_secret)
    access_token = data["access_token"]
    log.info("[AUTH] Step 4 OK — access_token obtained")
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
            log.info("[AUTH] ✓ Cached token valid")
            return kite
        except Exception:
            log.info("[AUTH] Cached token expired, re-logging in")

    # Full login
    for attempt in range(1, 4):
        try:
            token = _do_login(api_key, api_secret, user_id, password, totp_secret)
            kite.set_access_token(token)
            kite.profile()
            _save_token(api_key, token)
            log.info(f"[AUTH] ✓ Login successful on attempt {attempt}")
            return kite
        except RuntimeError as e:
            log.error(f"[AUTH] Fatal: {e}")
            raise
        except Exception as e:
            log.error(f"[AUTH] Attempt {attempt} failed: {e}")
            if attempt < 3:
                time.sleep(10)

    raise RuntimeError("All login attempts failed")
