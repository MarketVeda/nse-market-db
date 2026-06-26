#!/usr/bin/env python3
"""
fetch_news.py — INCREMENTAL news and announcements fetcher
----------------------------------------------------------
Runs hourly during market hours AND at 6 PM daily.
Only fetches announcements NOT already in the news file.
Tracks seen announcement IDs to avoid duplicates.

FIXES in this version:
  1. Fetch window: days=1 → days=7  (gap-resilient)
  2. seen_ids expiry: 7 → 30 days   (matches rolling window)
  3. SCORE_MAP: 5 bugs fixed —
       a) "Disclosure under SEBI Takeover Regulations" was 17 → now 5
          (routine SAST promoter disclosure, NOT an actual takeover)
       b) "Bagging/Receiving of orders/contracts" was 5 → now 20
          (genuine order win)
       c) "Analysts/Institutional Investor Meet" was 5 → now 13
          (management guidance event)
       d) "Acquisition" (bare subject) was falling through to 5 → now 15
       e) "Clarification - Financial Results" was hitting score=13
          via 'financial results' match → now 5 (low-signal exchange query)
  4. board_meeting single dict overwrite → board_meetings[] list
     (preserves all upcoming meetings, not just last one fetched)
  5. pdf_url double-prefix bug fixed
     (attchmntFile already contains full URL path — was prefixing base URL twice)
  6. New fields: guidance_flag, pdf_url, has_guidance_event,
     next_result_date, next_result_purpose
  7. BACKFILL: on each run, re-scores all existing announcements with
     the corrected SCORE_MAP (one-time cost, idempotent after first pass)
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta, timezone

def get_ist_now():
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).replace(tzinfo=None)

import json, time, logging, hashlib
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

try:
    from nse import NSE
    NSE_LIB = True
except ImportError:
    log.warning("nse library not installed. Run: pip install nse httpx[http2]")
    NSE_LIB = False

NIFTY500_SET = {
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
}

# ── NSE base URL for PDF filing downloads ────────────────────────────────────
NSE_BASE = "https://nsearchives.nseindia.com/"

# ── Guidance event subjects — management gave forward outlook ─────────────────
GUIDANCE_SUBJECTS = {
    "analysts/institutional investor meet/con. call updates",
    "analyst meet", "investor meet", "investor presentation",
    "con. call update", "conference call update",
    "management meet", "management presentation", "roadshow", "earnings call",
}

# ── SCORE_MAP ─────────────────────────────────────────────────────────────────
# Checked in order: first match wins.
# Special pre-check in impact_score(): 'clarification' prefix → always 5.
# Negative exclusions checked immediately after that.
_NEGATIVES = [
    "penalty imposed","fine imposed","sebi action","sebi order","fraud",
    "default on","insolvency","scam","investigation by","ban imposed",
    "suspension of","criminal","nclt order","attachment of","show cause",
]
_SCORE_MAP = [
    (20, ["order win","order bagged","order received","contract awarded",
          "bagging/receiving","bagging of orders","receiving of orders",
          "lakh crore order","billion dollar order","mega order",
          "loi received","letter of intent"]),
    (18, ["index inclusion","added to nifty","nifty addition","sensex addition"]),
    (17, ["acquisition completed","merger approved","merger completed",
          "amalgamation approved","takeover offer","open offer launched",
          "open offer completed"]),
    (15, ["large order","major order","significant order","order worth",
          "crore order","acquisition of","acquires","acquiring","proposes to acquire",
          "major contract","strategic agreement signed","new project awarded",
          "order inflow","acquisition"]),
    (13, ["financial results","quarterly results","q1 results","q2 results",
          "q3 results","q4 results","annual results","fy results",
          "record profit","highest ever profit","all time high profit",
          "analysts/institutional investor meet","analyst meet","investor meet",
          "con. call update","conference call update","investor presentation",
          "management meet","management presentation","roadshow"]),
    (12, ["buyback","buy-back","share repurchase","regulatory approval",
          "sebi approval","rbi approval","drug approval","fda approval",
          "ema approval","nclat approval","nclt approval","cci approval",
          "environmental clearance"]),
    (10, ["dividend","bonus share","stock split","rights issue","record date",
          "capex","expansion plan","new plant","capacity addition",
          "commencement of commercial production","commencement of operations",
          "commercial operations commenced","press release","fund raising",
          "fundraise","qip","preferential allotment","ipo","fpo"]),
    (8,  ["outcome of board meeting","board meeting outcome","agm","egm",
          "credit rating upgrade","rating upgrade","rating revised upward"]),
    (5,  ["trading window","general updates","updates","shareholders meeting",
          "esop","esos","esps","newspaper publication","copy of newspaper",
          "change in director","change in management","appointment",
          "resignation","cessation","allotment","loss of share",
          "credit rating","credit rating-","disclosure under sebi",
          "disclosure of material","scheme of arrangement","sale or disposal",
          "agreements","tie up","promoter buying","bulk deal","block deal",
          "spurt in volume","price movement","corrigendum","committee meeting",
          "news verification","clarification"]),
]


def impact_score(text: str) -> int:
    t = text.lower().strip()
    # Clarification subjects are ALWAYS low-signal (score=5) regardless of content.
    # Must be checked before score=13 keywords fire on 'financial results'.
    if t.startswith("clarification") or t.startswith("reply to clarification"):
        return 5
    if any(k in t for k in _NEGATIVES):
        return 0
    for score, kws in _SCORE_MAP:
        if any(k in t for k in kws):
            return score
    return 5


def is_guidance_event(text: str) -> bool:
    t = text.lower().strip()
    return any(g in t for g in GUIDANCE_SUBJECTS)


def make_pdf_url(attach_field: str) -> str:
    """
    NSE attchmntFile field sometimes contains the full URL, sometimes just the path.
    Always normalise to a clean https://nsearchives.nseindia.com/... URL.
    """
    if not attach_field:
        return ""
    f = attach_field.strip()
    # Strip any accidental base-URL prefix before re-applying it
    f = f.replace(NSE_BASE, "").lstrip("/")
    return NSE_BASE + f if f else ""


def ann_id(ann: dict) -> str:
    key = f"{ann.get('symbol','')}{ann.get('exchdisstime','')}{ann.get('desc','')[:50]}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def safe(v) -> str:
    return str(v)[:300] if v else ""


SEEN_LOG  = Path("data/news/seen_ids.json")
NEWS_FILE = Path("data/news/news.json")


def load_seen_ids() -> set:
    try:
        if SEEN_LOG.exists():
            raw = json.loads(SEEN_LOG.read_text())
            cutoff = (get_ist_now() - timedelta(days=30)).strftime("%Y-%m-%d")
            return {k for k, v in raw.items() if v >= cutoff}
    except Exception:
        pass
    return set()


def save_seen_ids(seen: set, existing_log: dict):
    today = get_ist_now().strftime("%Y-%m-%d")
    for sid in seen:
        existing_log[sid] = today
    cutoff = (get_ist_now() - timedelta(days=30)).strftime("%Y-%m-%d")
    pruned = {k: v for k, v in existing_log.items() if v >= cutoff}
    SEEN_LOG.parent.mkdir(parents=True, exist_ok=True)
    SEEN_LOG.write_text(json.dumps(pruned, indent=2))


def load_news_file() -> dict:
    try:
        if NEWS_FILE.exists():
            return json.loads(NEWS_FILE.read_text())
    except Exception:
        pass
    return {
        "data_type":   "NEWS_ANNOUNCEMENTS",
        "description": "NSE corporate announcements — incremental, deduped, rolling 30 days",
        "source":      "NSE India official API",
        "symbols":     {}
    }


def ensure_sym(news_data: dict, sym: str):
    """Ensure symbol exists with correct schema. Migrates legacy board_meeting dict → list."""
    if sym not in news_data["symbols"]:
        news_data["symbols"][sym] = {
            "announcements":  [],
            "actions":        [],
            "board_meetings": [],
        }
        return
    d = news_data["symbols"][sym]
    # Migrate old single board_meeting dict to board_meetings list
    if "board_meeting" in d:
        old_bm = d.pop("board_meeting")
        if "board_meetings" not in d:
            d["board_meetings"] = [old_bm] if (old_bm and old_bm.get("meeting_date")) else []
    if "board_meetings" not in d:
        d["board_meetings"] = []


def backfill_scores(news_data: dict):
    """
    Re-score ALL existing announcements with the corrected SCORE_MAP.
    Also adds guidance_flag and pdf_url fields if missing.
    Idempotent — safe to run on every startup.
    """
    rescored = 0
    for sym, d in news_data["symbols"].items():
        ensure_sym(news_data, sym)
        for a in d.get("announcements", []):
            subj = a.get("subject", "")
            new_score = impact_score(subj)
            new_guidance = is_guidance_event(subj)
            changed = (a.get("score") != new_score or
                       "guidance_flag" not in a or
                       "pdf_url" not in a)
            if changed:
                a["score"] = new_score
                a["guidance_flag"] = new_guidance
                if "pdf_url" not in a:
                    a["pdf_url"] = ""   # can't reconstruct URL for old entries
                rescored += 1
        for m in d.get("board_meetings", []):
            subj = m.get("purpose", "")
            m["score"] = impact_score(subj)
            if "guidance_flag" not in m:
                m["guidance_flag"] = is_guidance_event(subj)
    log.info(f"Backfill: re-scored {rescored} existing announcements")


def main():
    log.info("=== News Incremental Fetch Start ===")
    today   = get_ist_now().strftime("%Y-%m-%d")
    now_str = get_ist_now().strftime("%H:%M")
    from_dt = get_ist_now() - timedelta(days=7)   # 7-day lookback, gap-resilient

    try:
        seen_raw = json.loads(SEEN_LOG.read_text()) if SEEN_LOG.exists() else {}
    except Exception:
        seen_raw = {}
    seen_ids  = load_seen_ids()
    news_data = load_news_file()

    # Migrate all existing symbols to correct schema + re-score with fixed SCORE_MAP
    for sym in list(news_data["symbols"].keys()):
        ensure_sym(news_data, sym)
    backfill_scores(news_data)

    log.info(f"Already seen: {len(seen_ids)} announcement IDs")
    new_count = 0

    if not NSE_LIB:
        log.warning("nse library not available — skipping fetch")
    else:
        try:
            with NSE("/tmp/nse_news_cache", server=True) as nse:

                # ── 1. Announcements ─────────────────────────────────────────
                try:
                    anns = nse.announcements(
                        index="equities",
                        from_date=from_dt,
                        to_date=get_ist_now()
                    )
                    log.info(f"NSE returned {len(anns)} raw announcements")
                    for a in anns:
                        sym = (a.get("symbol") or "").upper().strip()
                        if sym not in NIFTY500_SET:
                            continue
                        aid = ann_id({"symbol": sym,
                                      "exchdisstime": a.get("exchdisstime",""),
                                      "desc": a.get("desc","")})
                        if aid in seen_ids:
                            continue
                        subject  = safe(a.get("desc") or a.get("subject") or "")
                        pdf_file = safe(a.get("attchmntFile",""))
                        entry = {
                            "id":            aid,
                            "datetime":      safe(a.get("exchdisstime","")),
                            "subject":       subject,
                            "category":      safe(a.get("anncategory","")),
                            "score":         impact_score(subject),
                            "guidance_flag": is_guidance_event(subject),
                            "has_pdf":       bool(pdf_file),
                            "pdf_url":       make_pdf_url(pdf_file),
                            "fetched":       now_str,
                        }
                        ensure_sym(news_data, sym)
                        news_data["symbols"][sym]["announcements"].append(entry)
                        seen_ids.add(aid)
                        new_count += 1
                except Exception as e:
                    log.error(f"Announcements fetch error: {e}")

                # ── 2. Corporate actions ─────────────────────────────────────
                try:
                    actions = nse.actions()
                    for a in actions:
                        sym = (a.get("symbol") or "").upper().strip()
                        if sym not in NIFTY500_SET:
                            continue
                        aid = ann_id({"symbol": sym,
                                      "exchdisstime": str(a.get("exDate","")),
                                      "desc": a.get("subject","")})
                        if aid in seen_ids:
                            continue
                        subject = safe(a.get("subject") or a.get("purpose") or "")
                        entry = {
                            "id":      aid,
                            "ex_date": safe(a.get("exDate") or a.get("recordDate") or ""),
                            "action":  subject,
                            "score":   impact_score(subject),
                            "fetched": now_str,
                        }
                        ensure_sym(news_data, sym)
                        news_data["symbols"][sym]["actions"].append(entry)
                        seen_ids.add(aid)
                        new_count += 1
                except Exception as e:
                    log.error(f"Actions fetch error: {e}")

                # ── 3. Board meetings ─────────────────────────────────────────
                # Stored as list — all upcoming meetings preserved per symbol.
                # Purpose field: "Q1 FY27 Results", "Interim Dividend", "Fund Raising"
                # next_result_date computed from this list at summary step below.
                try:
                    meetings = nse.boardMeetings(fno=False)
                    for m in meetings:
                        sym = (m.get("symbol") or "").upper().strip()
                        if sym not in NIFTY500_SET:
                            continue
                        purpose = safe(m.get("purpose") or m.get("bm_desc") or "")
                        date_   = safe(m.get("bm_date") or m.get("meetingDate") or "")
                        aid     = ann_id({"symbol": sym, "exchdisstime": date_, "desc": purpose})
                        if aid in seen_ids:
                            continue
                        entry = {
                            "id":            aid,
                            "meeting_date":  date_,
                            "purpose":       purpose,
                            "score":         impact_score(purpose),
                            "guidance_flag": is_guidance_event(purpose),
                            "fetched":       now_str,
                        }
                        ensure_sym(news_data, sym)
                        news_data["symbols"][sym]["board_meetings"].append(entry)
                        seen_ids.add(aid)
                        new_count += 1
                except Exception as e:
                    log.error(f"Board meetings error: {e}")

        except Exception as e:
            log.error(f"NSE client error: {e}")

    # ── Prune old entries ─────────────────────────────────────────────────────
    cutoff = (get_ist_now() - timedelta(days=30)).strftime("%Y-%m-%d")
    for sym, d in news_data["symbols"].items():
        d["announcements"] = [
            a for a in d.get("announcements", [])
            if a.get("datetime","") >= cutoff or not a.get("datetime","")
        ][-50:]
        d["board_meetings"] = [
            m for m in d.get("board_meetings", [])
            if m.get("meeting_date","") >= cutoff or not m.get("meeting_date","")
        ][-10:]

    # ── Compute per-symbol summary fields ────────────────────────────────────
    for sym, d in news_data["symbols"].items():
        all_scores = (
            [a.get("score",0) for a in d.get("announcements",[])] +
            [a.get("score",0) for a in d.get("actions",[])] +
            [m.get("score",0) for m in d.get("board_meetings",[])]
        )
        d["news_impact_score"]       = max(all_scores) if all_scores else 0
        d["has_major_announcement"]  = d["news_impact_score"] >= 15
        d["exclude_negative"]        = d["news_impact_score"] == 0 and bool(d.get("announcements"))
        d["has_guidance_event"]      = (
            any(a.get("guidance_flag") for a in d.get("announcements",[])) or
            any(m.get("guidance_flag") for m in d.get("board_meetings",[]))
        )
        # next upcoming board meeting where purpose mentions results
        result_meetings = sorted(
            [m for m in d.get("board_meetings",[])
             if "result" in m.get("purpose","").lower()
             and m.get("meeting_date","") >= today],
            key=lambda x: x["meeting_date"]
        )
        d["next_result_date"]    = result_meetings[0]["meeting_date"] if result_meetings else ""
        d["next_result_purpose"] = result_meetings[0]["purpose"]      if result_meetings else ""

    # ── Write outputs ─────────────────────────────────────────────────────────
    news_data["last_updated"]    = f"{today} {now_str}"
    news_data["description"]     = "NSE corporate announcements — incremental, deduped, rolling 30 days"
    news_data["total_symbols"]   = len(news_data["symbols"])
    news_data["high_impact"]     = sum(1 for v in news_data["symbols"].values() if v.get("news_impact_score",0) >= 15)
    news_data["guidance_events"] = sum(1 for v in news_data["symbols"].values() if v.get("has_guidance_event"))
    news_data["new_this_run"]    = new_count
    news_data["total_seen_ids"]  = len(seen_ids)

    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(news_data, indent=2, default=str))
    save_seen_ids(seen_ids, seen_raw)

    log.info(
        f"=== News Done: +{new_count} new | {len(news_data['symbols'])} symbols | "
        f"{news_data['high_impact']} high-impact | {news_data['guidance_events']} guidance events ==="
    )


if __name__ == "__main__":
    main()
