#!/usr/bin/env python3
"""
fetch_eod.py — EOD OHLCV + DMA + RS for NIFTY 500
---------------------------------------------------
INCREMENTAL: Skips fetch if today's file already exists and has >490 symbols.
PRUNING:     Deletes files older than 3 trading days after successful fetch.
             (History is INSIDE each file — 5 years = ~1260 candles per symbol)
Output: data/daily/YYYY-MM-DD.json  (one file per trading day, keep last 3)

HISTORY POLICY:
  Each daily file contains FULL OHLCV history arrays per symbol (5 years).
  This enables VCP pattern detection, pivot analysis, multi-timeframe RS,
  ATR tightness, Stage analysis, Darvas Box — all from a single file.
  File size: ~35–45 MB per day. Keep last 3 = ~120 MB stable.
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta, timezone

def get_ist_now():
    """Always returns current time as IST — GitHub runners use UTC."""
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)

import json, time, logging
from pathlib import Path
from kite_auth import get_kite

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

KEEP_DAYS    = 3     # keep last 3 daily files (each ~40 MB → ~120 MB stable)
HISTORY_DAYS = 1825  # 5 years of daily candles (~1260 trading days)

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
    today    = get_ist_now().strftime("%Y-%m-%d")
    weekday  = get_ist_now().weekday()
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


def rs_score_period(sc, nc, period):
    """RS over a specific lookback — used for multi-period RS table."""
    if len(sc) < period or len(nc) < period:
        return None
    sr = (sc[-1]-sc[-period])/sc[-period]
    nr = (nc[-1]-nc[-period])/nc[-period]
    return round(sr/nr if nr!=0 else 0.0, 4)


def compute_atr(candles, period=14):
    """Average True Range over last `period` candles."""
    if len(candles) < period + 1:
        return None
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    recent = trs[-period:]
    return round(sum(recent) / len(recent), 2)


def main():
    log.info("=== EOD Fetch Start ===")
    kite     = get_kite()
    today    = get_ist_now()
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

    start     = today - timedelta(days=HISTORY_DAYS)
    token_map = build_instrument_map(kite)

    # Fetch Nifty50 index history (token 256265) for RS calculation
    nifty_candles = []
    nifty_closes  = []
    try:
        nifty_candles = safe_fetch(kite, 256265, "day", start, today)
        nifty_closes  = [c["close"] for c in nifty_candles]
        log.info(f"Nifty50: {len(nifty_closes)} candles, last={nifty_closes[-1]}")
    except Exception as e:
        log.warning(f"Nifty50 failed: {e}")

    output = {
        "data_type":        "EOD_DAILY",
        "description":      "End-of-Day OHLCV full history + DMA + RS for NIFTY 500",
        "universe":         "NIFTY500 (500 symbols)",
        "fetch_date":       date_str,
        "fetch_time":       today.strftime("%H:%M:%S IST"),
        "source":           "Zerodha Kite Connect Historical API",
        "history_days":     HISTORY_DAYS,
        "nifty50_close":    nifty_closes[-1] if nifty_closes else 0,
        "nifty50_history":  [{"d": c["date"].strftime("%Y-%m-%d") if hasattr(c["date"],"strftime") else str(c["date"])[:10],
                              "o": c["open"], "h": c["high"], "l": c["low"],
                              "c": c["close"], "v": c.get("volume", 0)}
                             for c in nifty_candles],
        "symbols":          {}
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

            # ── Build compact OHLCV history arrays ──────────────────────────
            # Stored as parallel arrays (not list-of-dicts) to keep file lean.
            # dates[] aligns 1:1 with opens[], highs[], lows[], closes[], vols[]
            dates  = []
            opens  = []
            highs  = []
            lows_a = []
            closes = []
            vols   = []
            for c in candles:
                d = c["date"]
                dates.append(d.strftime("%Y-%m-%d") if hasattr(d,"strftime") else str(d)[:10])
                opens.append(round(c["open"],  2))
                highs.append(round(c["high"],  2))
                lows_a.append(round(c["low"],  2))
                closes.append(round(c["close"], 2))
                vols.append(c.get("volume", 0))

            # ── Latest candle summary ────────────────────────────────────────
            tc  = candles[-1]
            pc  = candles[-2] if len(candles) >= 2 else candles[-1]
            n   = len(closes)
            v_clean = [v for v in vols if v > 0]

            # ── Pre-computed indicators (avoid re-computing in scanner) ──────
            dma_50  = round(sum(closes[-50:]) /min(n,50),  2) if n >= 10  else None
            dma_150 = round(sum(closes[-150:])/min(n,150), 2) if n >= 50  else None
            dma_200 = round(sum(closes[-200:])/min(n,200), 2) if n >= 100 else None

            # Multi-period RS for relative strength ranking
            rs_65   = rs_score_period(closes, nifty_closes, 65)
            rs_126  = rs_score_period(closes, nifty_closes, 126)   # ~6 months
            rs_252  = rs_score_period(closes, nifty_closes, 252)   # ~1 year
            rs_raw  = rs_65  # backward-compatible primary RS field

            # ATR for VCP tightness / stop-loss sizing
            atr_14  = compute_atr(candles, 14)
            atr_21  = compute_atr(candles, 21)

            # 52-week high/low from actual history window
            highs_all = [c["high"]  for c in candles]
            lows_all  = [c["low"]   for c in candles if c["low"] > 0]
            # True 52w = last 252 trading days
            w52_hi = round(max(highs_all[-252:] if n >= 252 else highs_all), 2)
            w52_lo = round(min(lows_all[-252:]  if len(lows_all) >= 252 else lows_all), 2) if lows_all else 0

            # Volume averages at multiple windows
            avg_vol_10  = int(sum(v_clean[-10:]) /min(len(v_clean),10))  if v_clean else 0
            avg_vol_20  = int(sum(v_clean[-20:]) /min(len(v_clean),20))  if v_clean else 0
            avg_vol_50  = int(sum(v_clean[-50:]) /min(len(v_clean),50))  if v_clean else 0

            # Minervini Stage 2 flags (pre-computed for fast filtering)
            close_now = tc["close"]
            minervini_pass = bool(
                dma_50 and dma_150 and dma_200 and
                close_now > dma_50 and
                close_now > dma_150 and
                close_now > dma_200 and
                dma_50 > dma_150 and
                dma_150 > dma_200 and
                rs_raw is not None and rs_raw > 1.0 and
                close_now >= w52_hi * 0.75
            )

            output["symbols"][sym] = {
                # ── Today's summary (fast access, no array scan needed) ──────
                "open":         tc["open"],
                "high":         tc["high"],
                "low":          tc["low"],
                "close":        close_now,
                "volume":       tc.get("volume", 0),
                "prev_close":   pc["close"],
                "change_pct":   round(((close_now - pc["close"]) / pc["close"]) * 100, 2) if pc["close"] else 0,

                # ── Moving averages ──────────────────────────────────────────
                "dma_50":       dma_50,
                "dma_150":      dma_150,
                "dma_200":      dma_200,

                # ── Relative Strength ────────────────────────────────────────
                "rs_raw":       rs_raw,       # primary (65-day, backward compat)
                "rs_65":        rs_65,
                "rs_126":       rs_126,
                "rs_252":       rs_252,

                # ── Range / volatility ───────────────────────────────────────
                "52w_high":     w52_hi,
                "52w_low":      w52_lo,
                "atr_14":       atr_14,
                "atr_21":       atr_21,
                "atr_pct":      round(atr_14 / close_now * 100, 2) if atr_14 and close_now else None,

                # ── Volume averages ──────────────────────────────────────────
                "avg_vol_10":   avg_vol_10,
                "avg_vol_20":   avg_vol_20,
                "avg_vol_50":   avg_vol_50,

                # ── Minervini pre-filter ─────────────────────────────────────
                "minervini_pass": minervini_pass,

                # ── Full OHLCV history arrays ────────────────────────────────
                # Parallel arrays — index N of each array = same candle.
                # dates[0] is oldest, dates[-1] is today.
                "candle_count": n,
                "dates":        dates,
                "opens":        opens,
                "highs":        highs,
                "lows":         lows_a,
                "closes":       closes,
                "volumes":      vols,

                "data_grade":   "A",
            }

        except Exception as e:
            log.error(f"  FAILED {sym}: {e}")
            output["symbols"][sym] = {"error": str(e), "data_grade": "C"}
            failed.append(sym)
        time.sleep(0.34)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, default=str))
    ok       = sum(1 for v in output["symbols"].values() if v.get("data_grade") == "A")
    mp_count = sum(1 for v in output["symbols"].values() if v.get("minervini_pass"))
    log.info(f"=== EOD Done: {ok}/{len(NIFTY500)} OK | {mp_count} Minervini pass | {len(failed)} failed ===")

    # PRUNE: keep only last KEEP_DAYS files
    prune_old_files(out.parent, KEEP_DAYS)


if __name__ == "__main__":
    main()
