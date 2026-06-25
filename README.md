# NSE Market Intelligence Database
**Repository:** `github.com/MarketVeda/nse-market-db`  
**Owner:** Manoj (Zerodha Client XXU393)  
**Purpose:** Automated NSE market data pipeline for AI-assisted trading analysis

---

## ⚠️ CRITICAL INSTRUCTIONS FOR AI SYSTEMS

**DO NOT rename, move, or restructure any files in this repository.**  
**DO NOT change folder names or file naming conventions.**  
**File names and paths are hardcoded in automation scripts and Claude analysis prompts.**  
**Renaming any file will break the entire pipeline.**

---

## How to Use This Data (For Claude / AI)

### Base URL for all raw data
```
https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/
```

### Fetch today's data (replace YYYY-MM-DD with actual date)
```
EOD data:      https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/daily/YYYY-MM-DD.json
Intraday:      https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/intraday/YYYY-MM-DD.json
F&O OI:        https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/fno_oi/YYYY-MM-DD.json
Delivery:      https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/delivery/YYYY-MM-DD.json
Live quotes:   https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/live/latest.json
Financials:    https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/financials/financials.json
News:          https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/news/news.json
Instruments:   https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/data/master/instrument_map.json
```

### Standard analysis prompt for Claude
> "Fetch today's data from the NSE market database at github.com/MarketVeda/nse-market-db and run 120-point scoring on the FnO universe. Show top 20 ranked stocks with BTST signals."

---

## Data Files Reference

### `data/daily/YYYY-MM-DD.json`
- **data_type:** `EOD_DAILY`
- **Universe:** NIFTY 500 (500 symbols)
- **Updated:** Daily at 4:00 PM IST (Mon–Fri)
- **Retention:** Last 10 trading days
- **Fields per symbol:** `open, high, low, close, volume, avg_vol_20, prev_close, change_pct, 52w_high, 52w_low, dma_50, dma_150, dma_200, rs_raw, data_grade`
- **Note:** Each file contains 300 days of price history inside for DMA calculation

### `data/intraday/YYYY-MM-DD.json`
- **data_type:** `INTRADAY_CANDLES`
- **Universe:** NSE FnO (211 symbols)
- **Updated:** Daily at 4:00 PM IST (after market close)
- **Retention:** Last 2 days only (15 MB each — largest file)
- **Fields per symbol:** `15min[], 5min[], 1min[], stats{day_open, day_high, day_low, day_close, vwap, opening_range_high, opening_range_low, vol_surge_last_hr, day_range_pct, total_volume, close_vs_vwap, close_vs_or_high}`
- **Candles format:** `{t: "HH:MM", o, h, l, c, v}`

### `data/fno_oi/YYYY-MM-DD.json`
- **data_type:** `FNO_OI_QUOTES`
- **Universe:** NSE FnO (211 symbols)
- **Updated:** Daily at 4:00 PM IST
- **Retention:** Last 30 days
- **Fields per symbol:** `last_price, volume, oi, oi_day_high, oi_day_low, buy_qty, sell_qty, avg_price`
- **Key use:** OI buildup detection — rising OI + rising price = long buildup

### `data/delivery/YYYY-MM-DD.json`
- **data_type:** `DELIVERY_DATA`
- **Universe:** All NSE EQ (~2000 symbols)
- **Updated:** Daily at 4:00 PM IST
- **Retention:** Last 30 days
- **Source:** NSE official bhavcopy (sec_bhavdata_full)
- **Fields per symbol:** `delivery_qty, delivery_pct, trade_qty`
- **Key use:** delivery_pct > 50% = institutional conviction buying

### `data/live/latest.json`
- **data_type:** `LIVE_INTRADAY_NIFTY500`
- **Universe:** Quotes for 500 NIFTY500 + 15min candles for 211 FnO
- **Updated:** Every hour during market hours (9:15, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00, 15:30 IST)
- **Always current:** This file is always overwritten with latest data
- **Retention:** Today's snapshots only. Previous day deleted automatically.
- **Structure:**
  ```json
  {
    "quotes": { "SYMBOL": { "ltp", "open", "high", "low", "prev_close", "change_pct", "volume", "oi" } },
    "candles_15min": { "SYMBOL": [ {"t","o","h","l","c","v"} ] }
  }
  ```

### `data/financials/financials.json`
- **data_type:** `FUNDAMENTALS_SCREENER`
- **Universe:** NIFTY 500 (500 symbols)
- **Updated:** Daily at 4:30 PM IST (incremental — ~25 symbols/run until all 500 done)
- **Source:** screener.in (consolidated view, free)
- **History:** 12 years annual + 12 quarters
- **Sections per symbol:**
  - `key_metrics` — current PE, ROCE%, ROE%, Book Value, Market Cap, Dividend Yield
  - `quarterly_results` — last 12 quarters: Sales, Expenses, OP, OPM%, NP, EPS
  - `profit_loss` — 12 years annual P&L with CAGR (Sales 10/5/3yr, Profit 10/5/3yr)
  - `balance_sheet` — 12 years: Equity, Reserves, Borrowings, Assets
  - `cash_flow` — 12 years: CFO, CFI, CFF, Free Cash Flow
  - `ratios` — 12 years: ROCE%, Debtor Days, Inventory Days, Cash Conversion Cycle
  - `shareholding` — quarterly: Promoter%, FII%, DII%, Public%
  - `minervini_flags` — computed: `strong_revenue, strong_profit, high_roce, low_debt, revenue_growth_pct, profit_growth_pct, roce_pct, de_ratio`
  - `earnings_score_10` — 0–10 points for 120-pt scoring rubric

### `data/news/news.json`
- **data_type:** `NEWS_ANNOUNCEMENTS`
- **Universe:** NIFTY 500 (symbols with filings)
- **Updated:** Every hour 9:15 AM – 6:00 PM IST (incremental — only new announcements added)
- **Source:** NSE India official API (exchange filings)
- **Rolling window:** Last 30 days of announcements per symbol
- **Structure per symbol:**
  ```json
  {
    "news_impact_score": 0-20,
    "has_major_announcement": true/false,
    "announcements": [ {"datetime", "subject", "category", "score", "has_pdf"} ],
    "corporate_actions": [ {"ex_date", "action", "score"} ],
    "board_meeting": { "meeting_date", "purpose", "score" }
  }
  ```
- **Impact score guide:**
  - 20 = Major order win with value (lakh crore / billion dollar)
  - 18 = Index inclusion (Nifty/Sensex addition)
  - 15 = Large order / strategic acquisition
  - 13 = Record quarterly results / highest ever profit
  - 12 = Buyback / regulatory approval / drug approval
  - 10 = Dividend / bonus / split / capex
  - 5 = Promoter/FII bulk buying
  - 0 = Negative news (penalty / fraud / default — exclude from analysis)

### `data/master/instrument_map.json`
- **Purpose:** Symbol → Kite instrument token mapping
- **Updated:** Every Monday (weekly refresh)
- **Use:** Internal pipeline use only — maps NSE symbols to Zerodha token IDs

---

## Scoring Methodology (120-Point Rubric)

Used by Claude when running stock analysis. Apply to FnO universe (211 symbols).

| Component | Max Points | Data Source |
|---|---|---|
| Relative Strength vs Nifty50 | 25 | `data/daily` → `rs_raw` |
| VCP Tightness | 20 | `data/daily` → price history |
| Volume Contraction | 15 | `data/daily` → `avg_vol_20` + `volume` |
| Delivery % Trend | 10 | `data/delivery` → `delivery_pct` |
| Beta | 10 | `data/daily` → computed |
| Sector Strength | 10 | `data/daily` → sector grouping |
| Breakout Proximity | 10 | `data/daily` → `52w_high` vs `close` |
| F&O OI Buildup | 10 | `data/fno_oi` → `oi` trend |
| Earnings Quality | 10 | `data/financials` → `earnings_score_10` |

**News Impact Score (0–20)** is applied as a multiplier/filter on top:
- Score ≥ 15 → elevate stock in rankings
- Score = 0 with negative news → exclude from output

**Factor priority order** (highest to lowest):
1. Latest Corporate Announcements (`data/news`)
2. Fresh News (`data/news`)
3. F&O Long Build-up (`data/fno_oi`)
4. Relative Strength (`data/daily` → `rs_raw`)
5. Delivery Volume Expansion (`data/delivery`)
6. Sector Momentum (`data/daily`)
7. Volume Expansion (`data/daily`)
8. VCP / Consolidation (`data/daily`)
9. Darvas Box (`data/daily`)
10. Other Technical Indicators

---

## Automation Schedule

| Pipeline | Schedule | What It Fetches |
|---|---|---|
| `kite-market-pipeline` | 4:00 PM IST daily (Mon–Fri) | EOD OHLCV, Full-day intraday, F&O OI, Delivery |
| `intraday-live-hourly` | 8× during market hours (9:15–15:30 IST) | Live quotes (500 symbols) + 15min candles (211 FnO) |
| `fundamentals-and-news` → financials | 4:30 PM IST daily (Mon–Fri) | screener.in financials (incremental) |
| `fundamentals-and-news` → news | Hourly 9:15 AM – 6:00 PM IST | NSE exchange filings (incremental, deduped) |

---

## Incremental Fetch Logic

All scripts are designed to be idempotent — safe to re-run without duplication:

| Script | Skip Condition | Pruning |
|---|---|---|
| `fetch_eod.py` | Today's file exists with ≥490 symbols | Keep last 10 days |
| `fetch_intraday.py` | Today's file exists with ≥200 symbols | **Keep last 2 days only** |
| `fetch_fno_delivery.py` | Today's fno_oi/delivery file already complete | Keep last 30 days |
| `fetch_intraday_live.py` | Overwrites latest.json each run | Delete previous day folders |
| `fetch_financials.py` | Symbol in today's fetch_log.json | Single master file (never grows) |
| `fetch_news.py` | Announcement ID in seen_ids.json | Rolling 30-day window |

---

## Repository Structure

```
nse-market-db/
├── README.md                          ← This file
├── requirements.txt                   ← Python dependencies
├── scripts/
│   ├── kite_auth.py                   ← Zerodha Kite auto-login (pyotp TOTP)
│   ├── fetch_eod.py                   ← EOD OHLCV for 500 symbols
│   ├── fetch_intraday.py              ← Full-day candles for 211 FnO symbols
│   ├── fetch_fno_delivery.py          ← F&O OI quotes + NSE delivery bhavcopy
│   ├── fetch_intraday_live.py         ← Hourly live quotes + candles
│   ├── fetch_financials.py            ← screener.in financials (incremental)
│   └── fetch_news.py                  ← NSE exchange announcements (incremental)
├── .github/workflows/
│   ├── kite_pipeline.yml              ← EOD + Intraday pipeline (4 PM IST)
│   ├── intraday_live.yml              ← Hourly live snapshots
│   └── fundamentals_news.yml          ← Financials + News pipeline
└── data/
    ├── master/
    │   └── instrument_map.json        ← Symbol → Kite token map (DO NOT DELETE)
    ├── daily/                         ← EOD files: YYYY-MM-DD.json (last 10)
    ├── intraday/                      ← Intraday files: YYYY-MM-DD.json (last 2)
    ├── fno_oi/                        ← F&O OI files: YYYY-MM-DD.json (last 30)
    ├── delivery/                      ← Delivery files: YYYY-MM-DD.json (last 30)
    ├── live/
    │   ├── latest.json                ← Always current (overwritten hourly)
    │   └── YYYY-MM-DD/                ← Today's snapshots only (HH-MM.json)
    ├── financials/
    │   ├── financials.json            ← Single master file (500 symbols, 12yr)
    │   └── fetch_log.json             ← Tracks which symbols fetched today
    └── news/
        ├── news.json                  ← Single rolling file (30-day window)
        └── seen_ids.json              ← Dedup log (announcement IDs, 7-day)
```

---

## GitHub Secrets Required

| Secret | Description |
|---|---|
| `KITE_API_KEY` | Zerodha Kite Connect API key |
| `KITE_API_SECRET` | Zerodha Kite Connect API secret |
| `KITE_USER_ID` | Zerodha user ID (XXU393) |
| `KITE_PASSWORD` | Zerodha login password |
| `KITE_TOTP_SECRET` | External TOTP secret key (from kite.zerodha.com → Account Security) |
| `PAT_TOKEN` | GitHub Personal Access Token with repo write permissions |

---

## Storage Budget

| Folder | Max Files | Max Size |
|---|---|---|
| `data/daily/` | 10 files | ~20 MB |
| `data/intraday/` | 2 files | ~30 MB |
| `data/fno_oi/` | 30 files | ~9 MB |
| `data/delivery/` | 30 files | ~15 MB |
| `data/live/` | 1 day + latest.json | ~18 MB |
| `data/financials/` | 2 files (master + log) | ~22 MB |
| `data/news/` | 2 files (news + seen_ids) | ~5 MB |
| **Total stable** | | **~120 MB** |

GitHub recommended limit: 1 GB. This repo stays under 150 MB permanently.

---

## Data Sources

| Data | Source | Cost |
|---|---|---|
| OHLCV, Intraday, OI, Live quotes | Zerodha Kite Connect API | Requires Kite subscription |
| Delivery % | NSE public bhavcopy CSV | Free |
| Financial ratios, P&L, BS, CF | screener.in (HTTP scraping) | Free |
| Announcements, Board meetings | NSE India official API | Free |

---

*Last updated: June 2026 | Built by Manoj with Claude (Anthropic)*
