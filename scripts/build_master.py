#!/usr/bin/env python3
"""
build_master.py
---------------
Downloads Definedge master file (NSE Cash + NSE FnO) and builds a
symbol → token mapping JSON used by other scripts to call the raw REST API.

Run: python scripts/build_master.py
No env vars required (master file is public).
"""

import json
import zipfile
import logging
import requests
from io import BytesIO
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

MASTER_URLS = {
    "nsecash": "https://app.definedgesecurities.com/public/nsecash.zip",
    "nsefno":  "https://app.definedgesecurities.com/public/nsefno.zip",
}

# CSV columns per Definedge docs:
# SEGMENT, TOKEN, SYMBOL, TRADINGSYM, INSTRUMENT TYPE, EXPIRY, TICKSIZE,
# LOTSIZE, OPTIONTYPE, STRIKE, PRICEPREC, MULTIPLIER, ISIN, PRICEMULT, COMPANY
COL_TOKEN     = 1
COL_SYMBOL    = 2
COL_TRADINGSYM = 3
COL_SEGMENT   = 0
COL_INSTRUMENT = 4


def download_and_parse(url: str, segment_filter: str) -> dict:
    """Download zip, extract CSV, parse relevant rows."""
    log.info(f"Downloading {url}...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()

    result = {}
    with zipfile.ZipFile(BytesIO(resp.content)) as zf:
        for name in zf.namelist():
            if not name.endswith(".csv"):
                continue
            log.info(f"  Parsing {name}...")
            with zf.open(name) as f:
                lines = f.read().decode("utf-8", errors="replace").splitlines()

            for line in lines[1:]:   # skip header
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 5:
                    continue
                segment    = parts[COL_SEGMENT]
                instrument = parts[COL_INSTRUMENT] if len(parts) > COL_INSTRUMENT else ""
                symbol     = parts[COL_SYMBOL]
                tradingsym = parts[COL_TRADINGSYM]
                token      = parts[COL_TOKEN]

                # Only equity cash instruments (EQ) for NSE Cash
                if segment_filter == "NSE" and instrument != "EQ":
                    continue
                # For FnO, keep FUTSTK (futures) only
                if segment_filter == "NFO" and instrument != "FUTSTK":
                    continue

                if symbol:
                    result[symbol] = {
                        "token":      token,
                        "segment":    segment,
                        "tradingsym": tradingsym,
                        "instrument": instrument,
                    }

    return result


def main():
    mapping = {}

    # NSE Cash — equity tokens
    try:
        cash = download_and_parse(MASTER_URLS["nsecash"], "NSE")
        mapping.update(cash)
        log.info(f"  NSE Cash: {len(cash)} equity symbols")
    except Exception as e:
        log.error(f"NSE Cash master failed: {e}")

    # NSE FnO — futures tokens (overlapping symbols get FnO token, used for OI)
    try:
        fno = download_and_parse(MASTER_URLS["nsefno"], "NFO")
        for sym, data in fno.items():
            if sym in mapping:
                # Add fno token alongside equity token
                mapping[sym]["fno_token"]      = data["token"]
                mapping[sym]["fno_tradingsym"] = data["tradingsym"]
            else:
                mapping[sym] = data
        log.info(f"  NSE FnO: {len(fno)} futures symbols")
    except Exception as e:
        log.error(f"NSE FnO master failed: {e}")

    output = {
        "generated_date": datetime.today().strftime("%Y-%m-%d"),
        "generated_time": datetime.today().strftime("%H:%M:%S IST"),
        "source": "Definedge Securities master file",
        "total_symbols": len(mapping),
        "symbols": mapping,
    }

    out_dir  = Path("data/master")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "symbol_token_map.json"

    with open(out_path, "w") as f:
        json.dump(output, f, indent=2, default=str)

    log.info(f"✓ Saved {out_path}  |  {len(mapping)} total symbols")


if __name__ == "__main__":
    main()
