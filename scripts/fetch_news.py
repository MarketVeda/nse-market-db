#!/usr/bin/env python3
"""
fetch_news.py — INCREMENTAL news and announcements fetcher
----------------------------------------------------------
Runs hourly during market hours AND at 6 PM daily.
Only fetches announcements NOT already in the news file.
Tracks seen announcement IDs to avoid duplicates.

Logic:
  1. Load existing news file + seen_ids
  2. Fetch last 7 days of announcements (gap-safe; dedup prevents duplicates)
  3. Add only NEW IDs
  4. Save updated file + seen_ids log

FIXES vs original:
  - fetch window: days=1 → days=7 (gap-resilient)
  - seen_ids expiry: 7 → 30 days (matches announcement rolling window)
  - SCORE_MAP: fixed 3 false-positive bugs:
      a) "Disclosure under SEBI Takeover Regulations" was scoring 17 (matched "takeover")
         → now correctly scores 5 (routine promoter/investor disclosure, not an actual takeover)
      b) "Bagging/Receiving of orders/contracts" was scoring 5 (missed "order bagged")
         → now scores 20 correctly
      c) "Analyst/Investor Meet" was scoring 5 (no match)
         → now scores 13 (management guidance event — high signal for momentum traders)
  - board_meeting: was overwriting on every run (only last meeting kept per symbol)
         → now stored as a LIST, all upcoming meetings preserved
  - New field: "pdf_url" saved when attchmntFile present (Claude can fetch PDF later)
  - New field: "guidance_flag" set True when subject indicates forward guidance
  - New subject categories added to SCORE_MAP:
      "Financial Results" (13), "Investor Presentation" (13), "Press Release" (10),
      "Commencement of operations" (10), "New project" / "new contract" (15),
      "Credit Rating upgrade" (8), "Credit Rating downgrade" negative score
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta, timezone

def get_ist_now():
    """Always returns current time as IST — GitHub runners use UTC."""
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

# ── SCORE MAP ──────────────────────────────────────────────────────────────────
# Priority: negative exclusions checked FIRST, then positive matches top-to-bottom.
# All matching is done on lowercased subject text.
#
# CRITICAL RULES:
#   - "Disclosure under SEBI Takeover Regulations" = routine promoter holding
#     disclosure (SAST), NOT an actual takeover. Score: 5 (generic update).
#     Do NOT match "takeover" in the subject "Takeover Regulations".
#   - "Bagging/Receiving of orders/contracts" = genuine order win. Score: 20.
#   - "Analysts/Institutional Investor Meet" = management guidance event.
#     Score: 13 (forward guidance; high signal for momentum).
#   - "Financial Results" alone = 13 (actual result announcement).
#   - "Investor Presentation" = 13 (management guidance + strategy).
#   - "Clarification - Financial Results" = 5 (routine BSE query response).
# ──────────────────────────────────────────────────────────────────────────────

SCORE_MAP = [
    # ── Negative first — these EXCLUDE (score 0) ─────────────────────────────
    (0,  ["penalty imposed","fine imposed","sebi action","sebi order","fraud",
          "default on","insolvency","scam","investigation by","ban imposed",
          "suspension of","criminal","nclt order","attachment of","show cause"]),

    # ── Score 20 — Blockbuster order wins ────────────────────────────────────
    (20, ["order win","order bagged","order received","contract awarded",
          "bagging/receiving","bagging of orders","receiving of orders",
          "lakh crore order","billion dollar order","mega order",
          "loi received","letter of intent"]),

    # ── Score 18 — Index events ───────────────────────────────────────────────
    (18, ["index inclusion","added to nifty","nifty addition","sensex addition",
          "nifty50 inclusion","nifty 50 addition"]),

    # ── Score 17 — Confirmed M&A (completed, approved) ───────────────────────
    # NOTE: "Disclosure under SEBI Takeover Regulations" must NOT match here.
    # Use tight phrases that only appear in real M&A completions.
    (17, ["acquisition completed","merger approved","merger completed",
          "amalgamation approved","takeover offer","open offer launched",
          "open offer completed"]),

    # ── Score 15 — Large orders, acquisitions announced (not yet completed) ──
    (15, ["large order","major order","significant order","order worth",
          "crore order","acquisition of","acquires","acquiring","proposes to acquire",
          "major contract","strategic agreement signed","new project awarded",
          "order inflow"]),

    # ── Score 13 — Results + guidance events ─────────────────────────────────
    # "Financial Results" subject = actual result filing (high impact)
    # "Analyst/Investor Meet" = management gave guidance (forward-looking)
    # "Investor Presentation" = strategy/guidance deck filed with exchange
    (13, ["financial results","quarterly results","q1 results","q2 results",
          "q3 results","q4 results","annual results","fy results",
          "record profit","highest ever profit","all time high profit",
          "analysts/institutional investor meet","analyst meet","investor meet",
          "con. call update","conference call update","investor presentation",
          "management meet","management presentation","roadshow"]),

    # ── Score 12 — Regulatory approvals, buybacks ────────────────────────────
    (12, ["buyback","buy-back","share repurchase","regulatory approval",
          "sebi approval","rbi approval","drug approval","fda approval",
          "ema approval","nclat approval","nclt approval","cci approval",
          "environmental clearance"]),

    # ── Score 10 — Corporate actions + capex + new capacity ──────────────────
    (10, ["dividend","bonus share","stock split","rights issue","record date",
          "capex","expansion plan","new plant","capacity addition",
          "commencement of commercial production","commencement of operations",
          "commercial operations commenced","press release","fund raising",
          "fundraise","qip","preferential allotment","ipo","fpo"]),

    # ── Score 8 — Board meetings, AGM, credit rating upgrades ────────────────
    (8,  ["outcome of board meeting","board meeting outcome","agm","egm",
          "credit rating upgrade","rating upgrade","rating revised upward"]),

    # ── Score 5 — Generic disclosures, routine filings ───────────────────────
    # Includes "Disclosure under SEBI Takeover Regulations" (SAST routine filing)
    # Includes trading window, newspaper ads, general updates
    (5,  ["trading window","general updates","updates","shareholders meeting",
          "esop","esos","esps","newspaper publication","copy of newspaper",
          "change in director","change in management","appointment",
          "resignation","cessation","allotment","loss of share",
          "credit rating","credit rating-","disclosure under sebi",
          "disclosure of material","scheme of arrangement","sale or disposal",
          "agreements","tie up","promoter buying","bulk deal","block deal",
          "spurt in volume","price movement","corrigendum","committee meeting",
          "news verification","clarification"]),

    # ── Score 3 — Clarifications on results (not the result itself) ──────────
    (3,  ["clarification - financial","reply to clarification","board outcome"]),

    # ── Default fallback score for unmatched subjects ─────────────────────────
    # (handled in impact_score() function below)
]

# Subjects that indicate management gave FORWARD GUIDANCE (next quarter/year outlook)
# These get guidance_flag=True in the stored entry — useful for fundamental analysis
GUIDANCE_SUBJECTS = {
    "analysts/institutional investor meet/con. call updates",
    "analyst meet",
    "investor meet",
    "investor presentation",
    "con. call update",
    "conference call update",
    "management meet",
    "management presentation",
    "roadshow",
    "earnings call",
}


def impact_score(text: str) -> int:
    t = text.lower()
    # Check negatives first
    neg_kws = SCORE_MAP[0][1]
    if any(k in t for k in neg_kws):
        return 0
    # Then positive matches, highest score first
    for score, kws in SCORE_MAP[1:]:
        if any(k in t for k in kws):
            return score
    return 5   # default: generic but present


def is_guidance_event(text: str) -> bool:
    """True when the filing subject indicates mgmt gave forward guidance."""
    t = text.lower()
    return any(g in t for g in GUIDANCE_SUBJECTS)


def ann_id(ann: dict) -> str:
    """Generate stable unique ID for an announcement."""
    key = f"{ann.get('symbol','')}{ann.get('exchdisstime','')}{ann.get('desc','')[:50]}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


def safe(v) -> str:
    return str(v)[:300] if v else ""


SEEN_LOG  = Path("data/news/seen_ids.json")
NEWS_FILE = Path("data/news/news.json")


def load_seen_ids() -> set:
    try:
        if SEEN_LOG.exists():
            data = json.loads(SEEN_LOG.read_text())
            # Keep IDs from last 30 days (matches announcement rolling window)
            cutoff = (get_ist_now() - timedelta(days=30)).strftime("%Y-%m-%d")
            return {k for k, v in data.items() if v >= cutoff}
    except Exception:
        pass
    return set()


def save_seen_ids(seen: set, existing_log: dict):
    today = get_ist_now().strftime("%Y-%m-%d")
    for sid in seen:
        existing_log[sid] = today
    # Prune IDs older than 30 days
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
    if sym not in news_data["symbols"]:
        news_data["symbols"][sym] = {
            "announcements": [],
            "actions":       [],
            "board_meetings": [],   # LIST — all upcoming meetings, not just latest
        }
    # Migrate legacy single board_meeting dict → list
    if "board_meeting" in news_data["symbols"][sym] and "board_meetings" not in news_data["symbols"][sym]:
        old = news_data["symbols"][sym].pop("board_meeting")
        news_data["symbols"][sym]["board_meetings"] = [old] if old else []


def main():
    log.info("=== News Incremental Fetch Start ===")
    today   = get_ist_now().strftime("%Y-%m-%d")
    now_str = get_ist_now().strftime("%H:%M")
    # 7-day lookback — gap-resilient. seen_ids dedup ensures zero duplicates.
    from_dt = get_ist_now() - timedelta(days=7)

    try:
        seen_raw = json.loads(SEEN_LOG.read_text()) if SEEN_LOG.exists() else {}
    except Exception:
        seen_raw = {}
    seen_ids  = load_seen_ids()
    news_data = load_news_file()

    log.info(f"Already seen: {len(seen_ids)} announcement IDs")
    new_count = 0

    if not NSE_LIB:
        log.warning("nse library not available — skipping")
        return

    try:
        with NSE("/tmp/nse_news_cache", server=True) as nse:

            # ── 1. Announcements ─────────────────────────────────────────────
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
                        # PDF URL for later fetching — management presentations,
                        # result PDFs, investor presentations can be downloaded
                        # and parsed by Claude to extract guidance/numbers
                        "pdf_url":       f"https://nsearchives.nseindia.com/{pdf_file}" if pdf_file else "",
                        "fetched":       now_str,
                    }
                    ensure_sym(news_data, sym)
                    news_data["symbols"][sym]["announcements"].append(entry)
                    seen_ids.add(aid)
                    new_count += 1
            except Exception as e:
                log.error(f"Announcements fetch error: {e}")

            # ── 2. Corporate actions (dividend / bonus / split) ──────────────
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

            # ── 3. Board meetings (upcoming results dates + purpose) ──────────
            # FIXED: was overwriting a single dict on each run → lost all but last meeting.
            # Now stored as a list; duplicates prevented via seen_ids.
            # board_meetings list = upcoming Q result dates + AGM + capex decisions.
            # PURPOSE field is the key: "Q1 FY27 Results", "Interim Dividend",
            # "Fund Raising", "Buyback" — directly tells you what's coming.
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
                        "id":           aid,
                        "meeting_date": date_,
                        "purpose":      purpose,
                        "score":        impact_score(purpose),
                        "guidance_flag": is_guidance_event(purpose),
                        "fetched":      now_str,
                    }
                    ensure_sym(news_data, sym)
                    news_data["symbols"][sym]["board_meetings"].append(entry)
                    seen_ids.add(aid)
                    new_count += 1
            except Exception as e:
                log.error(f"Board meetings error: {e}")

    except Exception as e:
        log.error(f"NSE client error: {e}")

    # ── Prune old announcements (keep last 30 days per symbol, max 50) ────────
    cutoff = (get_ist_now() - timedelta(days=30)).strftime("%Y-%m-%d")
    for sym, data in news_data["symbols"].items():
        # Prune announcements
        data["announcements"] = [
            a for a in data.get("announcements", [])
            if a.get("datetime","") >= cutoff or not a.get("datetime","")
        ][-50:]
        # Prune board_meetings — keep only future meetings (or last 30 days)
        data["board_meetings"] = [
            m for m in data.get("board_meetings", [])
            if m.get("meeting_date","") >= cutoff or not m.get("meeting_date","")
        ][-10:]

    # ── Update summary scores per symbol ──────────────────────────────────────
    for sym, data in news_data["symbols"].items():
        all_scores = (
            [a.get("score",0) for a in data.get("announcements",[])] +
            [a.get("score",0) for a in data.get("actions",[])] +
            [m.get("score",0) for m in data.get("board_meetings",[])]
        )
        data["news_impact_score"]       = max(all_scores) if all_scores else 0
        data["has_major_announcement"]  = data["news_impact_score"] >= 15
        data["exclude_negative"]        = data["news_impact_score"] == 0 and bool(data.get("announcements"))
        # guidance_flag at symbol level — True if ANY announcement or board meeting
        # was a management guidance event (analyst meet, investor presentation, etc.)
        data["has_guidance_event"]      = any(
            a.get("guidance_flag") for a in data.get("announcements",[])
        ) or any(
            m.get("guidance_flag") for m in data.get("board_meetings",[])
        )
        # next_result_date — earliest upcoming board meeting with "results" in purpose
        result_meetings = sorted(
            [m for m in data.get("board_meetings",[])
             if "result" in m.get("purpose","").lower() and m.get("meeting_date","") >= today],
            key=lambda x: x["meeting_date"]
        )
        data["next_result_date"]   = result_meetings[0]["meeting_date"] if result_meetings else ""
        data["next_result_purpose"] = result_meetings[0]["purpose"]     if result_meetings else ""

    news_data["last_updated"]    = f"{today} {now_str}"
    news_data["total_symbols"]   = len(news_data["symbols"])
    news_data["high_impact"]     = sum(1 for v in news_data["symbols"].values() if v.get("news_impact_score",0) >= 15)
    news_data["guidance_events"] = sum(1 for v in news_data["symbols"].values() if v.get("has_guidance_event"))
    news_data["new_this_run"]    = new_count
    news_data["total_seen_ids"]  = len(seen_ids)

    NEWS_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWS_FILE.write_text(json.dumps(news_data, indent=2, default=str))
    save_seen_ids(seen_ids, seen_raw)

    log.info(f"=== News Done: +{new_count} new | {len(news_data['symbols'])} symbols | "
             f"{news_data['high_impact']} high-impact | {news_data['guidance_events']} guidance events ===")


if __name__ == "__main__":
    main()
