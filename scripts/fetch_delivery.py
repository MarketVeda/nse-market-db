#!/usr/bin/env python3
"""
fetch_delivery.py
-----------------
Fetches NSE delivery data from the public NSE bhavcopy (no API key needed).
Saves to data/delivery/YYYY-MM-DD.json.

NSE publishes delivery data ~1 hour after market close at:
https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_DDMMYYYY.csv

Run: python scripts/fetch_delivery.py
No env vars required (public data source).
"""

import json
import time
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path
from io import StringIO

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.nseindia.com/",
}

def fetch_bhavcopy(date: datetime) -> dict | None:
    """Download and parse NSE sec_bhavdata_full CSV for a given date."""
    date_str_nse = date.strftime("%d%m%Y")   # DDMMYYYY format for NSE URL
    url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{date_str_nse}.csv"

    log.info(f"Fetching bhavcopy from: {url}")
    try:
        # NSE requires a session cookie — first hit the main site
        session = requests.Session()
        session.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=10)
        time.sleep(1)

        resp = session.get(url, headers=NSE_HEADERS, timeout=30)
        if resp.status_code == 200:
            return parse_bhavcopy_csv(resp.text)
        else:
            log.warning(f"HTTP {resp.status_code} for {url}")
            return None
    except Exception as e:
        log.error(f"Failed to fetch bhavcopy: {e}")
        return None


def parse_bhavcopy_csv(csv_text: str) -> dict:
    """
    Parse sec_bhavdata_full CSV.
    Columns include: SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, LAST, PREVCLOSE,
                     TOTTRDQTY, TOTTRDVAL, TIMESTAMP, TOTALTRADES, ISIN,
                     DELIV_QTY, DELIV_PER
    """
    results = {}
    lines = csv_text.strip().split("\n")
    if len(lines) < 2:
        return results

    header = [h.strip() for h in lines[0].split(",")]
    col = {name: idx for idx, name in enumerate(header)}

    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < len(col):
            continue
        try:
            series = parts[col.get("SERIES", 1)]
            if series != "EQ":
                continue   # skip futures, bonds, ETFs

            symbol     = parts[col["SYMBOL"]]
            trade_qty  = int(parts[col["TOTTRDQTY"]]) if parts[col["TOTTRDQTY"]] else 0
            deliv_qty  = int(parts[col["DELIV_QTY"]]) if parts[col.get("DELIV_QTY", -1)] != -1 and parts[col["DELIV_QTY"]] else 0
            deliv_pct  = float(parts[col["DELIV_PER"]]) if col.get("DELIV_PER") and parts[col["DELIV_PER"]] else 0.0

            results[symbol] = {
                "delivery_qty": deliv_qty,
                "delivery_pct": round(deliv_pct, 2),
                "trade_qty":    trade_qty,
                "data_grade":   "A",
            }
        except (IndexError, ValueError, KeyError):
            continue

    return results


def main():
    today    = datetime.today()
    date_str = today.strftime("%Y-%m-%d")

    # Try today first, then yesterday (data may not be out yet if run before 4 PM)
    delivery_data = None
    used_date = None
    for days_back in range(0, 4):
        attempt_date = today - timedelta(days=days_back)
        if attempt_date.weekday() >= 5:   # skip weekends
            continue
        result = fetch_bhavcopy(attempt_date)
        if result:
            delivery_data = result
            used_date = attempt_date
            break
        time.sleep(2)

    if not delivery_data:
        log.error("Could not fetch bhavcopy for any recent date. Saving empty file.")
        delivery_data = {}

    output = {
        "fetch_date":    date_str,
        "data_date":     used_date.strftime("%Y-%m-%d") if used_date else "unknown",
        "fetch_time":    today.strftime("%H:%M:%S IST"),
        "source":        "NSE sec_bhavdata_full CSV",
        "total_symbols": len(delivery_data),
        "symbols":       delivery_data,
    }

    out_dir  = Path("data/delivery")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{date_str}.json"

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    log.info(f"✓ Saved {out_path}  |  {len(delivery_data)} symbols with delivery data")


if __name__ == "__main__":
    main()
