#!/usr/bin/env python3
"""
fetch_eod.py — EOD OHLCV + DMA + RS for NIFTY 500
---------------------------------------------------
INCREMENTAL: Skips fetch if today's file already exists and has >490 symbols.
PRUNING:     Deletes files older than 10 trading days after successful fetch.
             (History is INSIDE each file — 300 days of closes per symbol)
Output: data/daily/YYYY-MM-DD.json  (one file per trading day, keep last 10)
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import json, time, logging
from datetime import datetime, timedelta
from pathlib import Path
from kite_auth import get_kite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

KEEP_DAYS = 10   # keep last 10 daily files

NIFTY500 = [
    "360ONE","3MINDIA","ABB","ACC","ACMESOLAR","AIAENG","APLAPOLLO","AUBANK","AWL",
    "AADHARHFC","AARTIIND","AAVAS","ABBOTINDIA","ACE","ACUTAAS","ADANIENSOL","ADANIENT",
    "ADANIGREEN","ADANIPORTS","ADANIPOWER","ATGL","ABCAPITAL","ABFRL","ABLBL","ABREL",
    "ABSLAMC","CPPLUS","AEGISLOG","AEGISVOPAK","AFCONS","AFFLE","AJANTPHARM","ALKEM",
    "ABDL","AMBER","AMBUJACEM","ANANDRATHI","ANANTRAJ","ANGELONE","APARINDS","APOLLOHOSP",
    "APOLLOTYRE","APTUS","ASAHIINDIA","ASHOKLEY","ASIANPAINT","ASTERDM","ASTRAL",
    "ATHERENERG","ATUL","AUROPHARMA","AIIL","DMART","AXISBANK","BEML","BLS","BSE",
    "BAJAJ-AUTO","BAJFINANCE","BAJAJFINSV","BAJAJHLDNG","BAJAJHFL","BALKRISIND",
    "BALRAMCHIN","BANDHANBNK","BANKBARODA","BANKINDIA","MAHABANK","BATAINDIA","BAYERCROP",
    "BELRISE","BERGEPAINT","BDL","BEL","BHARATFORG","BHEL","BPCL","BHARTIARTL",
    "BHARTIHEXA","BIKAJI","GROWW","BIOCON","BSOFT","BLUEDART","BLUEJET","BLUESTARCO",
    "BBTC","BOSCHLTD","FIRSTCRY","BRIGADE","BRITANNIA","MAPMYINDIA","CCL","CESC",
    "CGPOWER","CIEINDIA","CRISIL","CANFINHOME","CANBK","CANHLIFE","CAPLIPOINT","CGCL",
    "CARBORUNIV","CARTRADE","CASTROLIND","CEATLTD","CEMPRO","CENTRALBK","CDSL","CHALET",
    "CHAMBLFERT","CHENNPETRO","CHOICEIN","CHOLAHLDNG","CHOLAFIN","CIPLA","CUB","CLEAN",
    "COALINDIA","COCHINSHIP","COFORGE","COHANCE","COLPAL","CAMS","CONCORDBIO","CONCOR",
    "COROMANDEL","CRAFTSMAN","CREDITACC","CROMPTON","CUMMINSIND","CYIENT","DCMSHRIRAM",
    "DLF","DOMS","DABUR","DALBHARAT","DATAPATTNS","DEEPAKFERT","DEEPAKNTR","DELHIVERY",
    "DEVYANI","DIVISLAB","DIXON","LALPATHLAB","DRREDDY","EIDPARRY","EIHOTEL","EICHERMOT",
    "ELECON","ELGIEQUIP","EMAMILTD","EMCURE","EMMVEE","ENDURANCE","ENGINERSIN","ERIS",
    "ESCORTS","ETERNAL","EXIDEIND","NYKAA","FEDERALBNK","FACT","FINCABLES","FSL",
    "FIVESTAR","FORCEMOT","FORTIS","GAIL","GVT&D","GMRAIRPORT","GABRIEL","GALLANTT",
    "GRSE","GICRE","GILLETTE","GLAND","GLAXO","GLENMARK","MEDANTA","GODIGIT","GPIL",
    "GODFRYPHLP","GODREJCP","GODREJIND","GODREJPROP","GRANULES","GRAPHITE","GRASIM",
    "GRAVITA","GESHIP","FLUOROCHEM","GMDCLTD","HEG","HBLENGINE","HCLTECH","HDBFS",
    "HDFCAMC","HDFCBANK","HDFCLIFE","HFCL","HAVELLS","HEROMOTOCO","HEXT","HSCL",
    "HINDALCO","HAL","HINDCOPPER","HINDPETRO","HINDUNILVR","HINDZINC","POWERINDIA",
    "HOMEFIRST","HONASA","HONAUT","HUDCO","HYUNDAI","ICICIBANK","ICICIGI","ICICIAMC",
    "ICICIPRULI","IDBI","IDFCFIRSTB","IFCI","IIFL","IRB","IRCON","ITCHOTELS","ITC",
    "ITI","INDGN","INDIACEM","INDIAMART","INDIANB","IEX","INDHOTEL","IOC","IOB","IRCTC",
    "IRFC","IREDA","IGL","INDUSTOWER","INDUSINDBK","NAUKRI","INFY","INOXWIND","INTELLECT",
    "INDIGO","IGIL","IKS","IPCALAB","JBCHEPHARM","JKCEMENT","JBMA","JKTYRE","JMFINANCIL",
    "JSWCEMENT","JSWDULUX","JSWENERGY","JSWINFRA","JSWSTEEL","JAINREC","JPPOWER",
    "J&KBANK","JINDALSAW","JSL","JINDALSTEL","JIOFIN","JUBLFOOD","JUBLINGREA","JUBLPHARMA",
    "JWL","JYOTICNC","KPRMILL","KEI","KPITTECH","KAJARIACER","KPIL","KALYANKJIL",
    "KARURVYSYA","KAYNES","KEC","KFINTECH","KIRLOSENG","KOTAKBANK","KIMS","LTF","LTTS",
    "LGEINDIA","LICHSGFIN","LTFOODS","LTM","LT","LATENTVIEW","LAURUSLABS","THELEELA",
    "LEMONTREE","LENSKART","LICI","LINDEINDIA","LLOYDSME","LODHA","LUPIN","MMTC","MRF",
    "MGL","M&MFIN","M&M","MANAPPURAM","MRPL","MANKIND","MARICO","MARUTI","MFSL",
    "MAXHEALTH","MAZDOCK","MEESHO","MINDACORP","MSUMI","MOTILALOFS","MPHASIS","MCX",
    "MUTHOOTFIN","NATCOPHARM","NBCC","NCC","NHPC","NLCINDIA","NMDC","NSLNISP","NTPCGREEN",
    "NTPC","NH","NATIONALUM","NAVA","NAVINFLUOR","NESTLEIND","NETWEB","NEULANDLAB",
    "NEWGEN","NAM-INDIA","NIVABUPA","NUVAMA","NUVOCO","OBEROIROLTY","ONGC","OIL",
    "OLAELEC","OLECTRA","PAYTM","ONESOURCE","OFSS","POLICYBZR","PCBL","PGEL","PIIND",
    "PNBHOUSING","PTCIL","PVRINOX","PAGEIND","PARADEEP","PATANJALI","PERSISTENT",
    "PETRONET","PFIZER","PHOENIXLTD","PWL","PIDILITIND","PINELABS","PIRAMALFIN",
    "PPLPHARMA","POLYMED","POLYCAB","POONAWALLA","PFC","POWERGRID","PREMIERENE",
    "PRESTIGE","PNB","RRKABEL","RBLBANK","RECLTD","RHIM","RITES","RADICO","RVNL",
    "RAILTEL","RAINBOW","RKFORGE","REDINGTON","RELIANCE","RPOWER","SBFC","SBICARD",
    "SBILIFE","SJVN","SRF","SAGILITY","SAILIFE","SAMMAANCAP","MOTHERSON","SAPPHIRE",
    "SARDAEN","SAREGAMA","SCHAEFFLER","SCHNEIDER","SCI","SHREECEM","SHRIRAMFIN",
    "SHYAMMETL","ENRIN","SIEMENS","SIGNATURE","SOBHA","SOLARINDS","SONACOMS","SONATSOFTW",
    "STARHEALTH","SBIN","SAIL","SUMICHEM","SUNPHARMA","SUNTV","SUNDARMFIN","SUPREMEIND",
    "SPLPETRO","SUZLON","SWANCORP","SWIGGY","SYNGENE","SYRMA","TBOTEK","TVSMOTOR",
    "TATACAP","TATACHEM","TATACOMM","TCS","TATACONSUM","TATAELXSI","TATAINVEST","TMCV",
    "TMPV","TATAPOWER","TATASTEEL","TATATECH","TTML","TECHM","TECHNOE","TEGA","TEJASNET",
    "TENNIND","NIACL","RAMCOCEM","THERMAX","TIMKEN","TITAGARH","TITAN","TORNTPHARM",
    "TORNTPOWER","TARIL","TRAVELFOOD","TRENT","TRIDENT","TRITURBINE","TIINDIA","UCOBANK",
    "UNOMINDA","UPL","UTIAMC","ULTRACEMCO","UNIONBANK","UBL","UNITDSPR","URBANCO",
    "USHAMART","VTL","VBL","VAML","VISL","VEDL","VOGL","VEDPOWER","VIJAYA","VMM",
    "IDEA","VOLTAS","WAAREEENER","WELCORP","WELSPUNLIV","WHIRLPOOL","WIPRO","WOCKPHARMA",
    "YESBANK","ZFCVINDIA","ZEEL","ZENTEC","ZENSARTECH","ZYDUSLIFE","ZYDUSWELL","ECLERX"
]


def prune_old_files(folder: Path, keep: int):
    files = sorted(folder.glob("*.json"))
    for f in files[:-keep]:
        f.unlink()
        log.info(f"Pruned: {f.name}")


def build_instrument_map(kite):
    map_path = Path("data/master/instrument_map.json")
    today    = datetime.today().strftime("%Y-%m-%d")
    weekday  = datetime.today().weekday()
    if map_path.exists() and weekday != 0:
        cached = json.loads(map_path.read_text())
        if cached.get("date") == today or weekday != 0:
            log.info(f"Using cached instrument map ({cached.get('date')})")
            return cached["tokens"]
    log.info("Building fresh instrument map from Kite...")
    instruments = kite.instruments("NSE")
    token_map   = {}
    for inst in instruments:
        if inst["instrument_type"] == "EQ":
            sym = inst["tradingsymbol"].replace("-EQ","")
            token_map[sym] = {"token": inst["instrument_token"], "tradingsym": inst["tradingsymbol"]}
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps({"date": today, "tokens": token_map}, indent=2))
    log.info(f"Instrument map built: {len(token_map)} symbols")
    return token_map


def safe_fetch(kite, token, interval, from_dt, to_dt):
    for attempt in range(3):
        try:
            return kite.historical_data(token, from_dt, to_dt, interval)
        except Exception as e:
            if attempt < 2:
                log.warning(f"Retry {attempt+1}: {e}")
                time.sleep(2**attempt)
            else:
                raise
    return []


def rs_score(sc, nc, period=65):
    if len(sc) < period or len(nc) < period:
        return 0.0
    sr = (sc[-1]-sc[-period])/sc[-period]
    nr = (nc[-1]-nc[-period])/nc[-period]
    return round(sr/nr if nr!=0 else 0.0, 4)


def main():
    log.info("=== EOD Fetch Start ===")
    kite     = get_kite()
    today    = datetime.today()
    date_str = today.strftime("%Y-%m-%d")
    out      = Path(f"data/daily/{date_str}.json")

    # INCREMENTAL: skip if today's file already has good data
    if out.exists():
        try:
            existing = json.loads(out.read_text())
            ok = sum(1 for v in existing.get("symbols",{}).values() if v.get("data_grade")=="A")
            if ok >= 490:
                log.info(f"Today's EOD already complete ({ok} symbols) — skipping fetch")
                return
            log.info(f"Partial file found ({ok} symbols) — re-fetching")
        except Exception:
            pass

    start     = today - timedelta(days=300)
    token_map = build_instrument_map(kite)

    nifty_closes = []
    try:
        nc = safe_fetch(kite, 256265, "day", start, today)
        nifty_closes = [c["close"] for c in nc]
        log.info(f"Nifty50: {len(nifty_closes)} candles, last={nifty_closes[-1]}")
    except Exception as e:
        log.warning(f"Nifty50 failed: {e}")

    output = {
        "data_type":     "EOD_DAILY",
        "description":   "End-of-Day OHLCV + DMA + RS for NIFTY 500",
        "universe":      "NIFTY500 (500 symbols)",
        "fetch_date":    date_str,
        "fetch_time":    today.strftime("%H:%M:%S IST"),
        "source":        "Zerodha Kite Connect Historical API",
        "nifty50_close": nifty_closes[-1] if nifty_closes else 0,
        "symbols":       {}
    }

    failed = []
    for i, sym in enumerate(NIFTY500, 1):
        inst = token_map.get(sym)
        if not inst:
            output["symbols"][sym] = {"error":"not_found","data_grade":"C"}
            continue
        log.info(f"[{i:3d}/{len(NIFTY500)}] {sym}")
        try:
            candles = safe_fetch(kite, inst["token"], "day", start, today)
            if not candles:
                raise ValueError("Empty")
            closes = [c["close"] for c in candles]
            highs  = [c["high"]  for c in candles]
            lows   = [c["low"]   for c in candles if c["low"]>0]
            vols   = [c["volume"] for c in candles if c.get("volume",0)>0]
            tc, pc = candles[-1], (candles[-2] if len(candles)>=2 else candles[-1])
            n      = len(closes)
            output["symbols"][sym] = {
                "open":       tc["open"],
                "high":       tc["high"],
                "low":        tc["low"],
                "close":      tc["close"],
                "volume":     tc.get("volume",0),
                "avg_vol_20": int(sum(vols[-20:])/min(len(vols),20)) if vols else 0,
                "prev_close": pc["close"],
                "change_pct": round(((tc["close"]-pc["close"])/pc["close"])*100,2) if pc["close"] else 0,
                "52w_high":   round(max(highs),2),
                "52w_low":    round(min(lows),2) if lows else 0,
                "dma_50":     round(sum(closes[-50:])/min(n,50),2)   if n>=10  else None,
                "dma_150":    round(sum(closes[-150:])/min(n,150),2) if n>=50  else None,
                "dma_200":    round(sum(closes[-200:])/min(n,200),2) if n>=100 else None,
                "rs_raw":     rs_score(closes, nifty_closes),
                "data_grade": "A",
            }
        except Exception as e:
            log.error(f"  FAILED {sym}: {e}")
            output["symbols"][sym] = {"error":str(e),"data_grade":"C"}
            failed.append(sym)
        time.sleep(0.34)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, default=str))
    ok = sum(1 for v in output["symbols"].values() if v.get("data_grade")=="A")
    log.info(f"=== EOD Done: {ok}/{len(NIFTY500)} OK | {len(failed)} failed ===")

    # PRUNE: keep only last KEEP_DAYS files
    prune_old_files(out.parent, KEEP_DAYS)


if __name__ == "__main__":
    main()
