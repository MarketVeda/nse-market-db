#!/usr/bin/env python3
"""
fetch_fno_delivery.py
Part 1 → data/fno_oi/YYYY-MM-DD.json    : F&O OI + volume + buy/sell qty
Part 2 → data/delivery/YYYY-MM-DD.json  : NSE delivery qty + delivery % for ALL EQ symbols
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, logging, requests
from datetime import datetime, timedelta
from pathlib import Path
from kite_auth import get_kite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

FNO_SYMBOLS = [
    "360ONE","ABB","APLAPOLLO","AUBANK","ADANIENSOL","ADANIENT","ADANIGREEN",
    "ADANIPORTS","ADANIPOWER","ABCAPITAL","ALKEM","AMBER","AMBUJACEM","ANGELONE",
    "APOLLOHOSP","ASHOKLEY","ASIANPAINT","ASTRAL","AUROPHARMA","DMART","AXISBANK",
    "BSE","BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BAJAJHLDNG","BANDHANBNK","BANKBARODA",
    "BANKINDIA","BDL","BEL","BHARATFORG","BHEL","BPCL","BHARTIARTL","BIOCON",
    "BLUESTARCO","BOSCHLTD","BRITANNIA","CGPOWER","CANBK","CDSL","CHOLAFIN","CIPLA",
    "COALINDIA","COCHINSHIP","COFORGE","COLPAL","CAMS","CONCOR","CROMPTON","CUMMINSIND",
    "DLF","DABUR","DALBHARAT","DELHIVERY","DIVISLAB","DIXON","DRREDDY","ETERNAL",
    "EICHERMOT","EXIDEIND","FORCEMOT","NYKAA","FORTIS","GAIL","GVT&D","GMRAIRPORT",
    "GLENMARK","GODFRYPHLP","GODREJCP","GODREJPROP","GRASIM","HCLTECH","HDFCAMC",
    "HDFCBANK","HDFCLIFE","HAVELLS","HEROMOTOCO","HINDALCO","HAL","HINDPETRO",
    "HINDUNILVR","HINDZINC","POWERINDIA","HYUNDAI","ICICIBANK","ICICIGI","ICICIPRULI",
    "IDFCFIRSTB","ITC","INDIANB","IEX","IOC","IRFC","IREDA","INDUSTOWER","INDUSINDBK",
    "NAUKRI","INFY","INOXWIND","INDIGO","JINDALSTEL","JSWENERGY","JSWSTEEL","JIOFIN",
    "JUBLFOOD","KEI","KPITTECH","KALYANKJIL","KAYNES","KFINTECH","KOTAKBANK","LTF",
    "LICHSGFIN","LTM","LT","LAURUSLABS","LICI","LODHA","LUPIN","M&M","MANAPPURAM",
    "MANKIND","MARICO","MARUTI","MFSL","MAXHEALTH","MAZDOCK","MOTILALOFS","MPHASIS",
    "MCX","MUTHOOTFIN","NBCC","NHPC","NMDC","NTPC","NATIONALUM","NESTLEIND","NAM-INDIA",
    "NUVAMA","OBEROIROLTY","ONGC","OIL","PAYTM","OFSS","POLICYBZR","PGEL","PIIND",
    "PNBHOUSING","PAGEIND","PATANJALI","PERSISTENT","PETRONET","PIDILITIND","POLYCAB",
    "PFC","POWERGRID","PREMIERENE","PRESTIGE","PNB","RBLBANK","RECLTD","RADICO","RVNL",
    "RELIANCE","SBICARD","SBILIFE","SHREECEM","SRF","SAMMAANCAP","MOTHERSON","SHRIRAMFIN",
    "SIEMENS","SOLARINDS","SONACOMS","SBIN","SAIL","SUNPHARMA","SUPREMEIND","SUZLON",
    "SWIGGY","TATACONSUM","TVSMOTOR","TCS","TATAELXSI","TMPV","TATAPOWER","TATASTEEL",
    "TECHM","FEDERALBNK","INDHOTEL","PHOENIXLTD","TITAN","TORNTPHARM","TRENT","TIINDIA",
    "UNOMINDA","UPL","ULTRACEMCO","UNIONBANK","UNITDSPR","VBL","VEDL","VMM","IDEA",
    "VOLTAS","WAAREEENER","WIPRO","YESBANK","ZYDUSLIFE"
]


def fetch_fno_oi(kite, date_str):
    log.info("=== F&O OI Fetch Start ===")
    all_keys = [f"NSE:{s}-EQ" for s in FNO_SYMBOLS]
    output   = {
        "data_type":   "FNO_OI_QUOTES",
        "description": "F&O Open Interest + live quotes for FnO universe",
        "universe":    "NSE FnO (211 symbols)",
        "fetch_date":  date_str,
        "fetch_time":  datetime.today().strftime("%H:%M:%S IST"),
        "source":      "Zerodha Kite Connect Quotes API",
        "fields":      ["last_price","volume","oi","oi_day_high","oi_day_low",
                        "buy_qty","sell_qty","avg_price","data_grade"],
        "note":        "OI = Open Interest for equity futures. High OI + rising price = long buildup.",
        "symbols":     {}
    }

    for start in range(0, len(all_keys), 200):
        batch = all_keys[start:start+200]
        try:
            quotes = kite.quote(batch)
            for key, q in quotes.items():
                sym = key.replace("NSE:","").replace("-EQ","")
                output["symbols"][sym] = {
                    "last_price":  q.get("last_price", 0),
                    "volume":      q.get("volume", 0),
                    "oi":          q.get("oi", 0),
                    "oi_day_high": q.get("oi_day_high", 0),
                    "oi_day_low":  q.get("oi_day_low", 0),
                    "buy_qty":     q.get("buy_quantity", 0),
                    "sell_qty":    q.get("sell_quantity", 0),
                    "avg_price":   q.get("average_price", 0),
                    "data_grade":  "A",
                }
            time.sleep(0.5)
        except Exception as e:
            log.error(f"Quote batch [{start}:{start+200}] failed: {e}")
            time.sleep(2)

    out = Path(f"data/fno_oi/{date_str}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2))
    log.info(f"=== F&O OI Done: {out} | {len(output['symbols'])} symbols ===")


def parse_bhavcopy(csv_text):
    results = {}
    lines   = csv_text.strip().split("\n")
    if len(lines) < 2:
        return results
    header = [h.strip() for h in lines[0].split(",")]
    col    = {n:i for i,n in enumerate(header)}
    for line in lines[1:]:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 5:
            continue
        try:
            if parts[col.get("SERIES",1)] != "EQ":
                continue
            sym       = parts[col["SYMBOL"]]
            trade_qty = int(parts[col["TOTTRDQTY"]]) if parts[col.get("TOTTRDQTY","")] else 0
            deliv_qty = int(parts[col["DELIV_QTY"]]) if col.get("DELIV_QTY") and parts[col["DELIV_QTY"]] else 0
            deliv_pct = float(parts[col["DELIV_PER"]]) if col.get("DELIV_PER") and parts[col["DELIV_PER"]] else 0.0
            results[sym] = {
                "delivery_qty": deliv_qty,
                "delivery_pct": round(deliv_pct, 2),
                "trade_qty":    trade_qty,
                "data_grade":   "A"
            }
        except (IndexError, ValueError, KeyError):
            continue
    return results


def fetch_delivery(date_str):
    log.info("=== Delivery Data Fetch Start ===")
    today   = datetime.strptime(date_str, "%Y-%m-%d")
    headers = {
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer":         "https://www.nseindia.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }

    delivery_data = {}
    used_date     = None

    for days_back in range(0, 4):
        attempt = today - timedelta(days=days_back)
        if attempt.weekday() >= 5:
            continue
        url = f"https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_{attempt.strftime('%d%m%Y')}.csv"
        log.info(f"Trying bhavcopy: {url}")
        try:
            sess = requests.Session()
            sess.get("https://www.nseindia.com", headers=headers, timeout=10)
            time.sleep(1)
            resp = sess.get(url, headers=headers, timeout=30)
            if resp.status_code == 200 and len(resp.text) > 500:
                delivery_data = parse_bhavcopy(resp.text)
                used_date     = attempt
                log.info(f"Bhavcopy OK for {attempt.date()}: {len(delivery_data)} symbols")
                break
        except Exception as e:
            log.warning(f"Bhavcopy attempt failed: {e}")
        time.sleep(2)

    output = {
        "data_type":     "DELIVERY_DATA",
        "description":   "NSE delivery quantity and delivery % for all EQ series symbols",
        "universe":      "All NSE EQ symbols (~2000 symbols)",
        "fetch_date":    date_str,
        "data_date":     used_date.strftime("%Y-%m-%d") if used_date else "unknown",
        "source":        "NSE sec_bhavdata_full public CSV",
        "fields":        ["delivery_qty","delivery_pct","trade_qty","data_grade"],
        "note":          "delivery_pct > 50% = strong institutional interest. High delivery = conviction buying.",
        "total_symbols": len(delivery_data),
        "symbols":       delivery_data,
    }
    out = Path(f"data/delivery/{date_str}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2))
    log.info(f"=== Delivery Done: {out} | {len(delivery_data)} symbols ===")


def main():
    kite     = get_kite()
    date_str = datetime.today().strftime("%Y-%m-%d")
    fetch_fno_oi(kite, date_str)
    fetch_delivery(date_str)
    log.info("=== All F&O + Delivery Done ===")


if __name__ == "__main__":
    main()
