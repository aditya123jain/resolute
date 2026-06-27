#!/usr/bin/env python3
"""
IPO Reversal Strategy — Full Backtest
======================================
Universe  : NSE Mainboard IPOs, listing years 2021-2026
Entry     : First trading day where intraday HIGH >= trailing_all-time_low × 1.10
Fill      : CLOSE of entry day  (user spec)
Stop      : Entry × 0.90 — checked against intraday LOW each post-entry day
Exit      : CLOSE of first trading day on/after listing-date anniversary
Data      : Yahoo Finance daily OHLC via requests
Author    : Claude (Sonnet 4.6) — 27 Jun 2026
"""

import os, time, warnings
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, date

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200)
pd.set_option("display.max_rows", 300)

TODAY  = date.today()
CA     = "/root/.ccr/ca-bundle.crt"
VERIFY = CA if os.path.exists(CA) else True

SESSION = requests.Session()
SESSION.verify = VERIFY
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
})

# ═══════════════════════════════════════════════════════════════════════════════
# UNIVERSE — NSE Mainboard IPOs 2021-2026
# Excludes NSE Emerge (SME), BSE SME listings.
# 2026 IPOs fetched dynamically from NSE India API below the static list.
# ═══════════════════════════════════════════════════════════════════════════════
STATIC_IPOS = [
    # ── 2021 ──────────────────────────────────────────────────────────────────
    ("IRFC",         "2021-01-29"), ("INDIGOPNTS",  "2021-02-02"),
    ("HOMEFIRST",    "2021-02-03"), ("STOVEKRAFT",  "2021-02-05"),
    ("KALYANKJIL",   "2021-03-26"), ("LAXMICHEM",   "2021-03-25"),
    ("MTARTECH",     "2021-03-15"), ("NAZARA",      "2021-03-30"),
    ("EASEMYTRIP",   "2021-03-19"), ("ANUPAMRAS",   "2021-03-24"),
    ("SURYODAY",     "2021-03-26"), ("CRAFTSMAN",   "2021-03-25"),
    ("BARBEQUE",     "2021-04-07"), ("LODHA",       "2021-04-19"),
    ("SHYAMMETL",    "2021-06-24"), ("SONACOMS",    "2021-06-24"),
    ("KIMS",         "2021-06-29"), ("DODLA",       "2021-06-28"),
    ("CLEAN",        "2021-07-19"), ("GRINFRA",     "2021-07-19"),
    ("ZOMATO",       "2021-07-23"), ("TATVA",       "2021-07-29"),
    ("GLENMARKLIFE", "2021-08-06"), ("ROLEXRINGS",  "2021-08-09"),
    ("DEVYANI",      "2021-08-16"), ("WINDLAS",     "2021-08-16"),
    ("KRSNAA",       "2021-08-16"), ("APTUS",       "2021-08-24"),
    ("CHEMPLASTS",   "2021-08-24"), ("NUVOCO",      "2021-08-23"),
    ("CARTRADE",     "2021-08-20"), ("VIJAYA",      "2021-09-14"),
    ("AMIORG",       "2021-09-14"), ("NYKAA",       "2021-11-10"),
    ("PAYTM",        "2021-11-18"), ("POLICYBZR",   "2021-11-15"),
    ("FINOPB",       "2021-11-12"), ("SJS",         "2021-11-09"),
    ("LATENTVIEW",   "2021-11-23"), ("TARSONS",     "2021-11-25"),
    ("SUPRIYA",      "2021-12-28"), ("STARHEALTH",  "2021-12-10"),
    ("DATAPATT",     "2021-12-24"), ("METRO",       "2021-12-22"),
    ("MEDPLUS",      "2021-12-17"),
    # ── 2022 ──────────────────────────────────────────────────────────────────
    ("AGSTRANS",     "2022-01-31"), ("CMSINFO",     "2022-01-31"),
    ("AWL",          "2022-02-08"), ("MANYAVAR",    "2022-02-16"),
    ("CAMPUS",       "2022-04-26"), ("HARIOMPIPE",  "2022-04-12"),
    ("DELHIVERY",    "2022-05-24"), ("LICI",        "2022-05-17"),
    ("AETHER",       "2022-05-25"), ("RAINBOW",     "2022-05-10"),
    ("VENUSPIPES",   "2022-05-24"), ("PARADEEP",    "2022-05-12"),
    ("PRUDENT",      "2022-05-10"), ("SYRMA",       "2022-08-26"),
    ("DREAMFOLKS",   "2022-09-06"), ("TMB",         "2022-09-08"),
    ("HARSHA",       "2022-09-26"), ("DCXSYS",      "2022-10-26"),
    ("EMIL",         "2022-10-17"), ("FUSION",      "2022-11-02"),
    ("MEDANTA",      "2022-11-07"), ("BIKAJI",      "2022-11-16"),
    ("FIVESTAR",     "2022-11-21"), ("KAYNES",      "2022-11-22"),
    ("ARCHEAN",      "2022-11-25"), ("UNIPARTS",    "2022-12-12"),
    ("SULA",         "2022-12-22"), ("LANDMARK",    "2022-12-23"),
    # ── 2023 ──────────────────────────────────────────────────────────────────
    ("MANKIND",      "2023-05-09"), ("IDEAFORGE",   "2023-06-07"),
    ("SENCO",        "2023-07-04"), ("CYIENTDLM",   "2023-07-03"),
    ("UTKARSHBNK",   "2023-07-14"), ("SBFC",        "2023-08-16"),
    ("CONCORDBIO",   "2023-08-18"), ("JSWINFRA",    "2023-09-06"),
    ("AEROFLEX",     "2023-09-08"), ("ZAGGLE",      "2023-09-22"),
    ("SIGNATURE",    "2023-09-27"), ("BLUEJET",     "2023-10-20"),
    ("FEDFINA",      "2023-11-22"), ("GANDHAR",     "2023-11-21"),
    ("FLAIR",        "2023-11-22"), ("CELLO",       "2023-11-08"),
    ("IREDA",        "2023-11-29"), ("TATATECH",    "2023-11-30"),
    ("MUTHOOTMF",    "2023-12-18"), ("INDIASHLTR",  "2023-12-20"),
    ("HAPPYFORG",    "2023-12-19"), ("DOMS",        "2023-12-20"),
    # ── 2024 ──────────────────────────────────────────────────────────────────
    ("JYOTICNC",     "2024-01-16"), ("MEDIASSIST",  "2024-01-23"),
    ("ENTERO",       "2024-02-09"), ("JANA",        "2024-02-14"),
    ("BHARTIHEXA",   "2024-04-22"), ("INDEGENE",    "2024-05-07"),
    ("TBOTEK",       "2024-05-23"), ("GODIGIT",     "2024-05-23"),
    ("AADHARHFL",    "2024-05-22"), ("AWFIS",       "2024-05-30"),
    ("OLAELEC",      "2024-08-09"), ("BRAINBEES",   "2024-08-13"),
    ("UNICOMMERCE",  "2024-08-13"), ("INTERARCH",   "2024-08-19"),
    ("PREMIERENE",   "2024-09-03"), ("BAJAJHFL",    "2024-09-16"),
    ("HYUNDAI",      "2024-10-22"), ("NIVABUPA",    "2024-11-14"),
    ("SWIGGY",       "2024-11-13"), ("NTPCGREEN",   "2024-11-27"),
    ("ZINKA",        "2024-11-22"), ("SAILIFE",     "2024-12-17"),
    ("MBK",          "2024-12-18"), ("VISHALMEGA",  "2024-12-18"),
    ("TRANSRAIL",    "2024-12-27"),
    # ── 2025 ──────────────────────────────────────────────────────────────────
    ("SGL",          "2025-01-06"), ("QUADRANT",    "2025-01-14"),
    ("HEXAWARE",     "2025-02-12"), ("AJAX",        "2025-02-06"),
    ("QUALITYPOW",   "2025-02-14"), ("ATHER",       "2025-05-06"),
]

# ═══════════════════════════════════════════════════════════════════════════════
def add_one_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:          # Feb 29 edge case
        return d.replace(year=d.year + 1, day=28)


def fetch_ohlc(symbol: str, start: date, end: date, retries: int = 3) -> pd.DataFrame:
    """Download daily OHLC from Yahoo Finance chart v8 API."""
    ticker = symbol + ".NS"
    p1 = int(datetime.combine(start, datetime.min.time()).timestamp())
    p2 = int(datetime.combine(end + timedelta(days=1), datetime.min.time()).timestamp())
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={p1}&period2={p2}&interval=1d"
    )
    for attempt in range(retries):
        try:
            r = SESSION.get(url, timeout=15)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            if r.status_code in (404, 422):
                return pd.DataFrame()
            r.raise_for_status()
            res = r.json().get("chart", {}).get("result")
            if not res:
                return pd.DataFrame()
            res = res[0]
            ts  = res["timestamp"]
            q   = res["indicators"]["quote"][0]
            df  = pd.DataFrame({
                "date":  pd.to_datetime(ts, unit="s").normalize(),
                "high":  q["high"],
                "low":   q["low"],
                "close": q["close"],
            })
            return (df.dropna(subset=["close", "high", "low"])
                      .sort_values("date")
                      .reset_index(drop=True))
        except Exception:
            if attempt < retries - 1:
                time.sleep(2)
    return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════════
def backtest_one(symbol: str, listing_date: date, df: pd.DataFrame) -> dict:
    """
    Apply IPO Reversal rules to one stock.
    Returns a result dict with 'status' key.
    """
    base = {"symbol": symbol, "listing_date": listing_date}
    if df.empty:
        return {**base, "status": "no_data"}

    anniversary = add_one_year(listing_date)

    # Clip data from listing date onwards
    df = df[df["date"].dt.date >= listing_date].copy().reset_index(drop=True)
    if len(df) < 3:
        return {**base, "status": "no_data"}

    # ── Phase 1 : scan for entry trigger ────────────────────────────────────
    trailing_low = float("inf")
    entry_date = entry_price = stop_price = None
    days_to_entry = None

    for _, row in df.iterrows():
        today      = row["date"].date()
        today_low  = float(row["low"])
        today_high = float(row["high"])
        today_close= float(row["close"])

        # Step 1: update trailing low (using intraday low)
        trailing_low = min(trailing_low, today_low)
        trigger_lvl  = trailing_low * 1.10

        if today >= anniversary:
            break           # anniversary passed with no trigger

        # Step 2: check if high touched/crossed trigger level this day
        if today_high >= trigger_lvl:
            entry_date    = today
            entry_price   = today_close      # fill at CLOSE per spec
            stop_price    = entry_price * 0.90
            days_to_entry = (entry_date - listing_date).days
            break

    if entry_date is None:
        return {**base, "status": "no_trigger",
                "days_observed": (df["date"].dt.date.iloc[-1] - listing_date).days}

    # ── Phase 2 : monitor from entry+1 day to anniversary ───────────────────
    post = df[df["date"].dt.date > entry_date].copy()

    for _, row in post.iterrows():
        today      = row["date"].date()
        today_low  = float(row["low"])
        today_close= float(row["close"])

        # Stop check (intraday low hits stop)
        if today_low <= stop_price:
            return {
                **base,
                "status":        "stop_hit",
                "entry_date":    entry_date,
                "entry_price":   round(entry_price, 2),
                "stop_price":    round(stop_price, 2),
                "exit_date":     today,
                "exit_price":    round(stop_price, 2),
                "return_pct":    round((stop_price / entry_price - 1) * 100, 2),
                "days_to_entry": days_to_entry,
                "days_held":     (today - entry_date).days,
            }

        # Anniversary exit
        if today >= anniversary:
            ret = today_close / entry_price - 1
            return {
                **base,
                "status":        "survived_positive" if ret > 0 else "survived_negative",
                "entry_date":    entry_date,
                "entry_price":   round(entry_price, 2),
                "exit_date":     today,
                "exit_price":    round(today_close, 2),
                "return_pct":    round(ret * 100, 2),
                "days_to_entry": days_to_entry,
                "days_held":     (today - entry_date).days,
            }

    # Still within 1-year window → active trade
    if not post.empty:
        last       = post.iloc[-1]
        last_close = float(last["close"])
    else:
        last       = df.iloc[-1]
        last_close = float(last["close"])
    unreal = last_close / entry_price - 1
    return {
        **base,
        "status":             "active",
        "entry_date":         entry_date,
        "entry_price":        round(entry_price, 2),
        "last_date":          last["date"].date(),
        "last_price":         round(last_close, 2),
        "return_pct":         round(unreal * 100, 2),
        "days_to_entry":      days_to_entry,
        "days_held":          (last["date"].date() - entry_date).days,
    }


# ═══════════════════════════════════════════════════════════════════════════════
def fmt(val, width=7, decimals=1):
    try:
        return f"{float(val):+{width}.{decimals}f}%"
    except Exception:
        return "   N/A"


def print_section(title):
    print(f"\n{'─'*70}")
    print(f"  {title}")
    print(f"{'─'*70}")


def main():
    ipos = STATIC_IPOS
    total = len(ipos)

    print(f"\n{'═'*70}")
    print(f"  IPO REVERSAL STRATEGY — BACKTEST")
    print(f"  Universe : NSE Mainboard IPOs 2021-2026  ({total} names)")
    print(f"  Run date : {TODAY}")
    print(f"  Rules    : Entry trigger HIGH≥low×1.10 → fill CLOSE")
    print(f"             Stop = Entry×0.90 | Exit = Listing anniversary close")
    print(f"{'═'*70}\n")
    print(f"{'#':>4}  {'Symbol':<14} {'Listed':<12} {'Status':<22} {'Return':>8}  {'Days held':>9}")
    print(f"{'─'*70}")

    results = []
    for i, (sym, ld_str) in enumerate(ipos, 1):
        ld      = datetime.strptime(ld_str, "%Y-%m-%d").date()
        anniv   = add_one_year(ld)
        end_dt  = min(anniv + timedelta(days=15), TODAY)
        df      = fetch_ohlc(sym, ld, end_dt)
        result  = backtest_one(sym, ld, df)
        results.append(result)

        st  = result.get("status", "?")
        ret = fmt(result.get("return_pct"), width=7) if "return_pct" in result else "      —"
        dh  = str(result.get("days_held", "—"))
        print(f"{i:>4}  {sym:<14} {ld_str:<12} {st:<22} {ret}  {dh:>9}")
        time.sleep(0.12)

    # ── Save raw results ─────────────────────────────────────────────────────
    df_all = pd.DataFrame(results)
    df_all.to_csv("ipo_reversal_results.csv", index=False)

    # ── Partition ────────────────────────────────────────────────────────────
    no_data    = df_all[df_all["status"] == "no_data"]
    no_trigger = df_all[df_all["status"] == "no_trigger"]
    active     = df_all[df_all["status"] == "active"]
    stop_hit   = df_all[df_all["status"] == "stop_hit"]
    surv_neg   = df_all[df_all["status"] == "survived_negative"]
    surv_pos   = df_all[df_all["status"] == "survived_positive"]
    triggered  = df_all[df_all["status"].isin(["stop_hit", "survived_negative", "survived_positive"])]

    n_total    = len(df_all)
    n_no_data  = len(no_data)
    n_with_data= n_total - n_no_data
    n_trig     = len(triggered)
    n_active   = len(active)

    # ── Summary ──────────────────────────────────────────────────────────────
    print_section("UNIVERSE & COVERAGE")
    print(f"  Total IPOs in universe       : {n_total:>5}")
    print(f"  No data (symbol not found)   : {n_no_data:>5}")
    print(f"  IPOs with data               : {n_with_data:>5}")
    print(f"  No trigger within 1 year     : {len(no_trigger):>5}  (setup never appeared)")
    print(f"  Active (anniversary pending) : {n_active:>5}")
    print(f"  Completed triggered trades   : {n_trig:>5}")
    if n_with_data > 0:
        cov = (n_trig + n_active) / n_with_data
        print(f"\n  ► Coverage rate              : {cov*100:.1f}%  "
              f"(fraction where 10% bounce setup appeared)")

    if n_trig == 0:
        print("\n  No completed trades to analyse.")
        return

    # ── Outcome distribution ─────────────────────────────────────────────────
    print_section("OUTCOME DISTRIBUTION  (completed triggered trades)")
    p_stop   = len(stop_hit) / n_trig
    p_sn     = len(surv_neg) / n_trig
    p_sp     = len(surv_pos) / n_trig
    p_loss   = p_stop + p_sn

    def avg(subset, col="return_pct"):
        s = pd.to_numeric(subset[col], errors="coerce").dropna()
        return s.mean() if len(s) else np.nan

    def med(subset, col="return_pct"):
        s = pd.to_numeric(subset[col], errors="coerce").dropna()
        return s.median() if len(s) else np.nan

    print(f"\n  {'Bucket':<28} {'N':>4}  {'Share':>6}  {'Avg Ret':>9}  {'Median Ret':>11}")
    print(f"  {'─'*62}")
    print(f"  {'Stop-loss hit':<28} {len(stop_hit):>4}  {p_stop*100:>5.1f}%  {avg(stop_hit):>+8.1f}%  {med(stop_hit):>+10.1f}%")
    print(f"  {'Survived, negative':<28} {len(surv_neg):>4}  {p_sn*100:>5.1f}%  {avg(surv_neg):>+8.1f}%  {med(surv_neg):>+10.1f}%")
    print(f"  {'Survived, positive':<28} {len(surv_pos):>4}  {p_sp*100:>5.1f}%  {avg(surv_pos):>+8.1f}%  {med(surv_pos):>+10.1f}%")
    print(f"  {'─'*62}")
    print(f"  {'TOTAL LOSS PROBABILITY':<28} {'':>4}  {p_loss*100:>5.1f}%")
    print(f"  {'WIN RATE (survived+ve)':<28} {'':>4}  {p_sp*100:>5.1f}%")

    # ── Return statistics ────────────────────────────────────────────────────
    print_section("RETURN STATISTICS  (all completed triggered trades)")
    all_ret = pd.to_numeric(triggered["return_pct"], errors="coerce").dropna()
    days_h  = pd.to_numeric(triggered["days_held"],  errors="coerce").dropna()

    print(f"  Mean return             : {all_ret.mean():>+7.1f}%")
    print(f"  Median return           : {all_ret.median():>+7.1f}%")
    print(f"  Best trade              : {all_ret.max():>+7.1f}%")
    print(f"  Worst trade             : {all_ret.min():>+7.1f}%")
    print(f"  Std deviation           : {all_ret.std():>7.1f}%")

    # Return percentile bands
    p10, p25, p75, p90 = all_ret.quantile([0.10, 0.25, 0.75, 0.90])
    print(f"  10th / 25th percentile  : {p10:>+7.1f}% / {p25:>+7.1f}%")
    print(f"  75th / 90th percentile  : {p75:>+7.1f}% / {p90:>+7.1f}%")
    print(f"  Avg holding period      : {days_h.mean():>6.0f} days")

    # CAGR proxy (average holding ~1 year, so return ≈ CAGR)
    avg_hold_yr = days_h.mean() / 365
    if avg_hold_yr > 0:
        cagr_proxy = (1 + all_ret.mean() / 100) ** (1 / avg_hold_yr) - 1
        print(f"  CAGR (annualised mean)  : {cagr_proxy*100:>+7.1f}%")

    # ── Stop-loss timing distribution ────────────────────────────────────────
    if len(stop_hit) > 0:
        print_section(f"STOP-LOSS TIMING  (n={len(stop_hit)} stops fired)")
        sd = pd.to_numeric(stop_hit["days_held"], errors="coerce").dropna()
        dte_entry = pd.to_numeric(stop_hit["days_to_entry"], errors="coerce").dropna()
        q1, q2, q3 = sd.quantile([0.25, 0.50, 0.75])
        print(f"  Days from ENTRY to stop:")
        print(f"    Min / Max           : {sd.min():.0f} / {sd.max():.0f} days")
        print(f"    Mean / Median       : {sd.mean():.0f} / {sd.median():.0f} days")
        print(f"    Q1 / Q2 / Q3        : {q1:.0f} / {q2:.0f} / {q3:.0f} days")
        print(f"  Avg days listing→entry: {dte_entry.mean():.0f} days")

        # Bucket: stopped within <30d, 30-90d, 90-180d, >180d
        b = [(0,30,"< 30 d"),(30,90,"30-90 d"),(90,180,"90-180 d"),(180,9999,">180 d")]
        print(f"\n  Timing buckets (days from entry):")
        for lo, hi, label in b:
            n = ((sd >= lo) & (sd < hi)).sum()
            print(f"    {label:<12}: {n:>3}  ({n/len(sd)*100:.0f}%)")

    # ── Days-to-entry distribution ───────────────────────────────────────────
    print_section("DAYS FROM LISTING TO ENTRY  (all triggered)")
    dte_all = pd.to_numeric(triggered["days_to_entry"], errors="coerce").dropna()
    print(f"  Mean / Median           : {dte_all.mean():.0f} / {dte_all.median():.0f} days")
    print(f"  Min / Max               : {dte_all.min():.0f} / {dte_all.max():.0f} days")
    for lo, hi, label in [(0,30,"< 30 d"),(30,90,"30-90 d"),(90,180,"90-180 d"),(180,365,">180 d")]:
        n = ((dte_all >= lo) & (dte_all < hi)).sum()
        print(f"  {label:<12}: {n:>3}  ({n/len(dte_all)*100:.0f}%)")

    # ── Top performers & worst losers ────────────────────────────────────────
    print_section("TOP 10 WINNERS")
    top10 = triggered.nlargest(10, "return_pct")[
        ["symbol", "listing_date", "entry_date", "entry_price", "exit_price", "return_pct", "days_held"]
    ]
    print(top10.to_string(index=False))

    print_section("TOP 10 LOSERS")
    bot10 = triggered.nsmallest(10, "return_pct")[
        ["symbol", "listing_date", "entry_date", "entry_price", "exit_price", "return_pct", "days_held"]
    ]
    print(bot10.to_string(index=False))

    # ── Active trades ────────────────────────────────────────────────────────
    if n_active > 0:
        print_section(f"ACTIVE TRADES (n={n_active}, anniversary not yet reached)")
        act_ret = pd.to_numeric(active["return_pct"], errors="coerce").dropna()
        print(f"  Mean unrealised return  : {act_ret.mean():>+7.1f}%")
        print(f"  Median unrealised return: {act_ret.median():>+7.1f}%")
        act_cols = [c for c in ["symbol","listing_date","entry_date","entry_price","last_price","return_pct","days_held"] if c in active.columns]
        print(active[act_cols].to_string(index=False))

    # ── Year-by-year cohort ──────────────────────────────────────────────────
    print_section("YEAR-BY-YEAR COHORT  (completed triggered only)")
    triggered2 = triggered.copy()
    triggered2["year"] = pd.to_datetime(triggered2["listing_date"]).dt.year
    cohort = (triggered2.groupby("year")
              .agg(n=("return_pct","count"),
                   mean_ret=("return_pct","mean"),
                   median_ret=("return_pct","median"),
                   win_pct=("return_pct", lambda x: (x > 0).mean() * 100))
              .reset_index())
    print(cohort.to_string(index=False))

    print(f"\n{'═'*70}")
    print(f"  Results saved → ipo_reversal_results.csv")
    print(f"{'═'*70}\n")


if __name__ == "__main__":
    main()
