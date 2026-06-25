# NSE Market Intelligence Database
**Repository:** `github.com/MarketVeda/nse-market-db`  
**Owner:** Manoj (Zerodha Client XXU393)  
**Last Updated:** June 2026  
**Purpose:** Fully automated NSE market data pipeline — OHLCV, intraday candles, F&O OI, delivery data, screener.in fundamentals, and NSE announcements — stored as JSON for AI-assisted trading analysis.

---

## ⚠️ CRITICAL: DO NOT RENAME ANY FILES

**File names, folder names, and paths are hardcoded in automation scripts and all analysis prompts.**  
**Renaming any file will break the entire pipeline silently.**  
**If you need to restructure, discuss first.**

---

## Quick Start — Base URL for All Data

```
https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/
```

**Always use this prefix + file path below to fetch any data file.**

---

## How to Fetch Data in Python

```python
import requests, json

BASE = "https://raw.githubusercontent.com/MarketVeda/nse-market-db/main/"

def fetch(path):
    url = BASE + path
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()

# Examples:
eod        = fetch("data/daily/2026-06-25.json")
intraday   = fetch("data/intraday/2026-06-25.json")
fno_oi     = fetch("data/fno_oi/2026-06-25.json")
delivery   = fetch("data/delivery/2026-06-25.json")
live       = fetch("data/live/latest.json")
financials = fetch("data/financials/financials.json")
news       = fetch("data/news/news.json")
```

**Replace date with today's date in YYYY-MM-DD format.**  
For live data, always use `data/live/latest.json` — it's always current.

---

## Complete Data File Reference

### 1. `data/daily/YYYY-MM-DD.json`
**What:** EOD OHLCV + DMA + Relative Strength for all 500 NIFTY500 symbols  
**Updated:** Daily at 4:00 PM IST (Mon–Fri) via `kite-market-pipeline`  
**Retention:** Last 10 trading days  
**Size:** ~2 MB per file  
**Source:** Zerodha Kite Connect Historical API  

```json
{
  "data_type": "EOD_DAILY",
  "fetch_date": "2026-06-25",
  "nifty50_close": 24500.0,
  "symbols": {
    "RELIANCE": {
      "open": 1420.0, "high": 1435.0, "low": 1415.0, "close": 1430.0,
      "volume": 5000000, "avg_vol_20": 4800000,
      "prev_close": 1415.0, "change_pct": 1.06,
      "52w_high": 1550.0, "52w_low": 1200.0,
      "dma_50": 1380.0, "dma_150": 1320.0, "dma_200": 1290.0,
      "rs_raw": 1.15,
      "data_grade": "A"
    }
  }
}
```

**Key fields:**
- `rs_raw` — Relative Strength vs Nifty50 over 65 days. >1.0 = outperforming
- `dma_50/150/200` — Moving averages. Minervini filter: price > all three
- `data_grade` — A = good data, C = failed fetch

---

### 2. `data/intraday/YYYY-MM-DD.json`
**What:** Full day candles (15min + 5min + 1min) for 211 FnO symbols  
**Updated:** Daily at 4:00 PM IST after market close  
**Retention:** Last 2 days only (each file is ~15 MB)  
**Source:** Zerodha Kite Connect Historical API  

```json
{
  "data_type": "INTRADAY_CANDLES",
  "fetch_date": "2026-06-25",
  "symbols": {
    "RELIANCE": {
      "15min": [{"t":"09:15","o":1420,"h":1425,"l":1418,"c":1422,"v":250000}, ...],
      "5min":  [{"t":"09:15","o":1420,"h":1422,"l":1419,"c":1421,"v":85000}, ...],
      "1min":  [{"t":"09:15","o":1420,"h":1421,"l":1420,"c":1420,"v":28000}, ...],
      "stats": {
        "day_open": 1420.0, "day_high": 1435.0, "day_low": 1415.0, "day_close": 1430.0,
        "day_change_pct": 1.06,
        "opening_range_high": 1425.0, "opening_range_low": 1418.0,
        "vwap": 1426.5,
        "vol_surge_last_hr": 1.35,
        "total_volume": 5000000,
        "close_vs_vwap": "above",
        "close_vs_or_high": "above"
      },
      "data_grade": "A"
    }
  }
}
```

**Key fields:**
- `stats.vwap` — Volume Weighted Average Price for the day
- `stats.vol_surge_last_hr` — Volume in last hour vs daily average. >1.5 = surge
- `stats.close_vs_or_high` — "above" means bullish close (Qullamaggie signal)

---

### 3. `data/fno_oi/YYYY-MM-DD.json`
**What:** F&O Open Interest + quotes for 211 FnO symbols  
**Updated:** Daily at 4:00 PM IST  
**Retention:** Last 30 days  
**Source:** Zerodha Kite Connect Quotes API  

```json
{
  "data_type": "FNO_OI_QUOTES",
  "fetch_date": "2026-06-25",
  "symbols": {
    "RELIANCE": {
      "last_price": 1430.0,
      "volume": 5000000,
      "oi": 12500000,
      "oi_day_high": 12800000,
      "oi_day_low": 12100000,
      "buy_qty": 250000,
      "sell_qty": 180000,
      "avg_price": 1426.5,
      "data_grade": "A"
    }
  }
}
```

**Key fields:**
- `oi` — Open Interest. Rising OI + rising price = long buildup (bullish)
- `oi` falling + rising price = short covering (also bullish)
- Compare across 2–3 days from different files to detect OI trend

---

### 4. `data/delivery/YYYY-MM-DD.json`
**What:** NSE delivery quantity and delivery % for all ~2500 EQ symbols  
**Updated:** Daily at 4:00 PM IST  
**Retention:** Last 30 days  
**Source:** NSE official bhavcopy (sec_bhavdata_full — public, free)  

```json
{
  "data_type": "DELIVERY_DATA",
  "fetch_date": "2026-06-25",
  "data_date": "2026-06-25",
  "total_symbols": 2488,
  "symbols": {
    "RELIANCE": {
      "delivery_qty": 2100000,
      "delivery_pct": 42.0,
      "trade_qty": 5000000,
      "data_grade": "A"
    }
  }
}
```

**Key fields:**
- `delivery_pct` — % of traded volume that was delivery-based
- >50% = institutional/conviction buying
- <20% = mostly intraday/speculative

---

### 5. `data/live/latest.json`
**What:** Hourly live snapshot — quotes for 500 NIFTY500 + 15min candles for 211 FnO  
**Updated:** Every hour during market hours (9:15, 10:00, 11:00, 12:00, 13:00, 14:00, 15:00, 15:30 IST)  
**Retention:** Today's snapshots only + latest.json (previous day deleted automatically)  
**Always use `latest.json`** — it is always the most recent snapshot  
**Source:** Zerodha Kite Connect  

```json
{
  "data_type": "LIVE_INTRADAY_NIFTY500",
  "snapshot_date": "2026-06-25",
  "snapshot_time": "13:00",
  "quotes_count": 496,
  "candles_count": 210,
  "quotes": {
    "RELIANCE": {
      "ltp": 1428.5, "open": 1420.0, "high": 1432.0, "low": 1415.0,
      "prev_close": 1415.0, "change": 13.5, "change_pct": 0.95,
      "volume": 3200000, "avg_price": 1424.0,
      "oi": 12400000, "buy_qty": 180000, "sell_qty": 120000
    }
  },
  "candles_15min": {
    "RELIANCE": [
      {"t":"09:15","o":1420,"h":1425,"l":1418,"c":1422,"v":250000},
      {"t":"09:30","o":1422,"h":1430,"l":1420,"c":1428,"v":310000}
    ]
  }
}
```

---

### 6. `data/financials/financials.json`
**What:** Complete fundamental data for all 500 NIFTY500 symbols — 12 years history  
**Updated:** Daily at 4:30 PM IST via `fetch-financials` workflow  
**Retention:** Single master file (never deleted, updated daily)  
**Size:** ~22 MB  
**Source:** screener.in (consolidated view, free)  

```json
{
  "data_type": "FUNDAMENTALS_SCREENER",
  "last_updated": "2026-06-25",
  "symbols": {
    "RELIANCE": {
      "data_grade": "A",
      "last_fetched": "2026-06-25",
      "view": "consolidated",
      "key_metrics": {
        "Market Cap": 1930000, "P/E": 28.5, "ROCE %": 11.5,
        "ROE %": 9.2, "Debt to equity": 0.41
      },
      "quarterly_results": {
        "headers": ["Jun 2024","Sep 2024","Dec 2024","Mar 2025","Jun 2025"],
        "rows": {
          "Sales": {"Jun 2024": 232000, "Sep 2024": 235000},
          "Net Profit": {"Jun 2024": 15000, "Sep 2024": 16200},
          "OPM %": {"Jun 2024": 17.2, "Sep 2024": 17.8}
        }
      },
      "profit_loss": { ... },
      "balance_sheet": { ... },
      "cash_flow": { ... },
      "ratios": { ... },
      "shareholding": {
        "rows": {
          "Promoters": {"Dec 2024": 50.3, "Mar 2025": 50.3},
          "FIIs": {"Dec 2024": 24.1, "Mar 2025": 24.5},
          "DIIs": {"Dec 2024": 15.8, "Mar 2025": 15.4}
        }
      },
      "minervini_flags": {
        "revenue_growth_pct": 18.5, "profit_growth_pct": 28.3,
        "roce_pct": 11.5, "de_ratio": 0.41, "fcf_positive": true,
        "strong_revenue": true, "strong_profit": true,
        "high_roce": false, "low_debt": true
      },
      "earnings_score_10": 7
    }
  }
}
```

**Key fields:**
- `minervini_flags` — Pre-computed Minervini SEPA criteria
- `earnings_score_10` — 0–10 score for use in 120-point scoring rubric
- `shareholding` — FII/DII/Promoter % trend across quarters

---

### 7. `data/news/news.json`
**What:** NSE corporate announcements — incremental, deduplicated, rolling 30 days  
**Updated:** Hourly 9:18 AM – 6:00 PM IST via `fetch-news` workflow  
**Retention:** Single rolling file (last 30 days per symbol)  
**Source:** NSE India official exchange filing API (free)  

```json
{
  "data_type": "NEWS_ANNOUNCEMENTS",
  "last_updated": "2026-06-25 15:33",
  "total_symbols": 209,
  "high_impact": 15,
  "symbols": {
    "CGPOWER": {
      "news_impact_score": 20,
      "has_major_announcement": true,
      "exclude_negative": false,
      "announcements": [
        {
          "datetime": "2026-06-25 11:30",
          "subject": "Order win worth Rs 2,500 Crore from defence sector",
          "category": "Order",
          "score": 20,
          "has_pdf": true
        }
      ],
      "actions": [
        {
          "ex_date": "2026-07-10",
          "action": "Dividend Rs 2.50 per share",
          "score": 10
        }
      ],
      "board_meeting": {
        "meeting_date": "2026-07-28",
        "purpose": "Q1 FY27 Results",
        "score": 13
      }
    }
  }
}
```

**Impact score guide (0–20):**
- 20 = Major order win (lakh crore / billion dollar scale)
- 18 = Index inclusion (Nifty/Sensex addition)
- 15 = Large order / strategic acquisition
- 13 = Record quarterly results / highest ever profit
- 12 = Buyback / regulatory/drug approval
- 10 = Dividend / bonus / split / capex announcement
- 5  = Promoter/FII bulk buying
- 0  = Negative (penalty / fraud / default — exclude from picks)

---

### 8. `data/master/instrument_map.json`
**What:** Symbol → Zerodha Kite instrument token mapping  
**Updated:** Every Monday  
**Use:** Internal pipeline only  

---

## Automation Pipelines

| Workflow | Cron (UTC) | IST Time | Script | Data Written |
|---|---|---|---|---|
| `kite-market-pipeline` | 30 10 * * 1-5 | 4:00 PM daily | fetch_eod + fetch_intraday + fetch_fno_delivery | daily/ intraday/ fno_oi/ delivery/ |
| `intraday-live-hourly` | 8 schedules | 9:15–15:30 hourly | fetch_intraday_live | live/latest.json |
| `fetch-financials` | 0 11 * * 1-5 | 4:30 PM daily | fetch_financials | financials/financials.json |
| `fetch-news` | 9 schedules | 9:18 AM–6 PM hourly | fetch_news | news/news.json |

---

## Incremental Fetch Design

All scripts are **idempotent** — safe to re-run without duplication:

| Script | Skip Condition | Pruning Policy |
|---|---|---|
| `fetch_eod.py` | Today's file has ≥490 symbols | Keep last 10 days |
| `fetch_intraday.py` | Today's file has ≥200 symbols | **Keep last 2 days only** |
| `fetch_fno_delivery.py` | Today's files already complete | Keep last 30 days |
| `fetch_intraday_live.py` | Overwrites latest.json always | Delete previous day folders |
| `fetch_financials.py` | Symbol in today's fetch_log.json | Single master file |
| `fetch_news.py` | Announcement ID in seen_ids.json | Rolling 30-day window |

---

## Scoring Methodology (120-Point Rubric)

Apply to FnO universe (211 symbols) for stock ranking:

| Factor | Max Points | Data Source | Field |
|---|---|---|---|
| Relative Strength vs Nifty50 | 25 | `data/daily/` | `rs_raw` |
| VCP Tightness | 20 | `data/daily/` | price history |
| Volume Contraction | 15 | `data/daily/` | `avg_vol_20` vs `volume` |
| Delivery % Trend | 10 | `data/delivery/` | `delivery_pct` |
| Beta | 10 | `data/daily/` | computed |
| Sector Strength | 10 | `data/daily/` | sector grouping |
| Breakout Proximity | 10 | `data/daily/` | `52w_high` vs `close` |
| F&O OI Buildup | 10 | `data/fno_oi/` | `oi` trend |
| Earnings Quality | 10 | `data/financials/` | `earnings_score_10` |

**News Impact Score (0–20)** from `data/news/` applied as overlay:
- Score ≥ 15 → elevate in final ranking
- Score = 0 with negative keyword → exclude entirely

**Factor Priority Order** (highest to lowest):
1. Corporate Announcements (`news.json` → `news_impact_score`)
2. Fresh News (`news.json` → `announcements`)
3. F&O Long Build-up (`fno_oi/` → `oi` trend)
4. Relative Strength (`daily/` → `rs_raw`)
5. Delivery Volume Expansion (`delivery/` → `delivery_pct`)
6. Sector Momentum (`daily/` → sector grouping)
7. Volume Expansion (`daily/` → `volume` vs `avg_vol_20`)
8. VCP / Consolidation (`daily/` → price range tightness)
9. Darvas Box (`daily/` → new highs on volume)
10. Other Technical Indicators

---

## Minervini SEPA Filters (apply before scoring)

All must be TRUE to qualify for BTST/swing consideration:

```python
close > dma_50        # Price above 50-day MA
close > dma_150       # Price above 150-day MA
close > dma_200       # Price above 200-day MA
dma_50 > dma_150      # 50 DMA above 150 DMA (uptrend)
dma_150 > dma_200     # 150 DMA above 200 DMA (stage 2)
rs_raw > 1.0          # Outperforming Nifty50
close >= 52w_high * 0.75   # Within 25% of 52-week high
```

---

## Repository Structure

```
nse-market-db/
├── README.md
├── requirements.txt
├── scripts/
│   ├── kite_auth.py           ← Zerodha Kite auto-login (pyotp TOTP)
│   ├── fetch_eod.py           ← EOD OHLCV for 500 NIFTY500 symbols
│   ├── fetch_intraday.py      ← Full-day candles for 211 FnO symbols
│   ├── fetch_fno_delivery.py  ← F&O OI quotes + NSE delivery bhavcopy
│   ├── fetch_intraday_live.py ← Hourly live quotes + candles
│   ├── fetch_financials.py    ← screener.in fundamentals (incremental)
│   └── fetch_news.py          ← NSE exchange announcements (incremental)
├── .github/workflows/
│   ├── kite_pipeline.yml      ← EOD + Intraday + FnO OI + Delivery
│   ├── intraday_live.yml      ← Hourly live snapshots
│   ├── fetch_financials.yml   ← Daily screener.in fundamentals
│   └── fetch_news.yml         ← Hourly NSE announcements
└── data/
    ├── master/
    │   └── instrument_map.json
    ├── daily/         YYYY-MM-DD.json  (last 10 days)
    ├── intraday/      YYYY-MM-DD.json  (last 2 days — 15 MB each)
    ├── fno_oi/        YYYY-MM-DD.json  (last 30 days)
    ├── delivery/      YYYY-MM-DD.json  (last 30 days)
    ├── live/
    │   ├── latest.json          ← always current
    │   └── YYYY-MM-DD/          ← today's snapshots only
    ├── financials/
    │   ├── financials.json      ← single master file (500 symbols)
    │   └── fetch_log.json       ← tracks which symbols fetched today
    └── news/
        ├── news.json            ← single rolling file (30-day window)
        └── seen_ids.json        ← dedup log (7-day expiry)
```

---

## Storage Budget

| Folder | Retention | Approx Size |
|---|---|---|
| `data/daily/` | Last 10 days | ~20 MB |
| `data/intraday/` | Last 2 days | ~30 MB |
| `data/fno_oi/` | Last 30 days | ~9 MB |
| `data/delivery/` | Last 30 days | ~15 MB |
| `data/live/` | Today + latest.json | ~18 MB |
| `data/financials/` | Single master file | ~22 MB |
| `data/news/` | Single rolling file | ~5 MB |
| **Total** | **Stable forever** | **~120 MB** |

GitHub recommended limit: 1 GB. This repo stays well under 150 MB permanently.

---

## GitHub Secrets Required

| Secret | Description |
|---|---|
| `KITE_API_KEY` | Zerodha Kite Connect API key |
| `KITE_API_SECRET` | Zerodha Kite Connect API secret |
| `KITE_USER_ID` | Zerodha user ID (XXU393) |
| `KITE_PASSWORD` | Zerodha login password |
| `KITE_TOTP_SECRET` | External TOTP secret from kite.zerodha.com → Account Security |
| `PAT_TOKEN` | GitHub Personal Access Token with repo write permissions |

---

## Data Sources

| Data | Source | Cost |
|---|---|---|
| OHLCV, Intraday, OI, Live | Zerodha Kite Connect API | Requires active Kite subscription |
| Delivery % | NSE official bhavcopy CSV | Free (public) |
| Fundamentals (P&L, BS, CF) | screener.in | Free (scraping) |
| Announcements, Board meetings | NSE India exchange API | Free (public) |

---

*Built by Manoj with Claude (Anthropic) — June 2026*
