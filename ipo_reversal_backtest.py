#!/usr/bin/env python3
"""
IPO Reversal Strategy — Full Backtest
======================================
Universe  : NSE Mainboard IPOs, FY20-FY27 (Apr 2019 – Mar 2027), ~402 names
Entry     : First trading day where intraday HIGH >= trailing_all-time_low × 1.10
Fill      : CLOSE of entry day  (user spec)
Stop      : Configurable via STOP_MODE (fixed / trailing / atr / time)
Exit      : CLOSE of first trading day on/after listing-date anniversary
Opt #2    : Compare four stop-loss modes side-by-side
Data      : Yahoo Finance daily OHLC (NSE bhavcopy fallback for YF-absent symbols)
Author    : Claude (Sonnet 4.6) — 27 Jun 2026
"""

import io, os, time, warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
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
# UNIVERSE — NSE Mainboard IPOs FY20-FY27 (Apr 2019 – Mar 2027)
# Symbols are the actual NSE trading symbols (from ipoplatform.com).
# Excludes NSE Emerge (SME), BSE SME, InvITs, REITs.
# ═══════════════════════════════════════════════════════════════════════════════
STATIC_IPOS = [
    # ── 2019 ────────────────────────────────────────────────────────────────────
    ("RVNL", "2019-04-11"),
    ("METROPOLIS", "2019-04-15"),
    ("POLYCAB", "2019-04-16"),
    ("NEOGEN", "2019-05-08"),
    ("INDIAMART", "2019-07-04"),
    ("AFFLE", "2019-08-08"),
    ("SPANDANA", "2019-08-19"),
    ("SWSOLAR", "2019-08-20"),
    ("IRCTC", "2019-10-14"),
    ("VISHWARAJ", "2019-10-15"),
    ("CSBBANK", "2019-12-04"),
    ("UJJIVANSFB", "2019-12-12"),
    ("PRINCEPIPE", "2019-12-30"),
    # ── 2020 ────────────────────────────────────────────────────────────────────
    ("SBICARD", "2020-03-16"),
    ("ROSSARI", "2020-07-23"),
    ("YESBANK", "2020-07-27"),
    ("HAPPSTMNDS", "2020-09-17"),
    ("ROUTE", "2020-09-21"),
    ("CHEMCON", "2020-10-01"),
    ("CAMS", "2020-10-01"),
    ("ANGELONE", "2020-10-05"),
    ("UTIAMC", "2020-10-12"),
    ("MAZDOCK", "2020-10-12"),
    ("LIKHITHA", "2020-10-15"),
    ("EQUITASBNK", "2020-11-02"),
    ("GLAND", "2020-11-20"),
    ("RBA", "2020-12-14"),
    ("BECTORFOOD", "2020-12-24"),
    # ── 2021 ────────────────────────────────────────────────────────────────────
    ("AWHCL", "2021-01-01"),
    ("IRFC", "2021-01-29"),
    ("INDIGOPNTS", "2021-02-02"),
    ("HOMEFIRST", "2021-02-03"),
    ("STOVEKRAFT", "2021-02-05"),
    ("NURECA", "2021-02-25"),
    ("RAILTEL", "2021-02-26"),
    ("HERANBA", "2021-03-05"),
    ("MTARTECH", "2021-03-15"),
    ("EASEMYTRIP", "2021-03-19"),
    ("ANURAS", "2021-03-24"),
    ("LXCHEM", "2021-03-25"),
    ("CRAFTSMAN", "2021-03-25"),
    ("SURYODAY", "2021-03-26"),
    ("KALYANKJIL", "2021-03-26"),
    ("NAZARA", "2021-03-30"),
    ("BARBEQUE", "2021-04-07"),
    ("LODHA", "2021-04-19"),
    ("SHYAMMETL", "2021-06-24"),
    ("SONACOMS", "2021-06-24"),
    ("KIMS", "2021-06-28"),
    ("DODLA", "2021-06-28"),
    ("IPL", "2021-07-05"),
    ("CLEAN", "2021-07-19"),
    ("GRINFRA", "2021-07-19"),
    ("ZOMATO", "2021-07-23"),
    ("TATVA", "2021-07-29"),
    ("GLS", "2021-08-06"),
    ("ROLEXRINGS", "2021-08-09"),
    ("KRSNAA", "2021-08-16"),
    ("DEVYANI", "2021-08-16"),
    ("WINDLAS", "2021-08-16"),
    ("EXXARO", "2021-08-16"),
    ("CARTRADE", "2021-08-20"),
    ("NUVOCO", "2021-08-23"),
    ("CHEMPLASTS", "2021-08-24"),
    ("APTUS", "2021-08-24"),
    ("AMIORG", "2021-09-14"),
    ("VIJAYA", "2021-09-14"),
    ("SANSERA", "2021-09-24"),
    ("PARAS", "2021-10-01"),
    ("ABSLAMC", "2021-10-11"),
    ("NYKAA", "2021-11-10"),
    ("FINOPB", "2021-11-12"),
    ("SJS", "2021-11-15"),
    ("POLICYBZR", "2021-11-15"),
    ("SIGACHI", "2021-11-15"),
    ("SAPPHIRE", "2021-11-18"),
    ("PAYTM", "2021-11-18"),
    ("LATENTVIEW", "2021-11-23"),
    ("TARSONS", "2021-11-26"),
    ("GOCOLORS", "2021-11-30"),
    ("STARHEALTH", "2021-12-10"),
    ("TEGA", "2021-12-13"),
    ("ANANDRATHI", "2021-12-14"),
    ("RATEGAIN", "2021-12-17"),
    ("SHRIRAMPPS", "2021-12-20"),
    ("MAPMYINDIA", "2021-12-21"),
    ("METROBRAND", "2021-12-22"),
    ("MEDPLUS", "2021-12-23"),
    ("DATAPATTNS", "2021-12-24"),
    ("HPAL", "2021-12-27"),
    ("SUPRIYA", "2021-12-28"),
    ("CMSINFO", "2021-12-31"),
    # ── 2022 ────────────────────────────────────────────────────────────────────
    ("AGSTRA", "2022-01-31"),
    ("AWL", "2022-02-08"),
    ("MANYAVAR", "2022-02-16"),
    ("UMAEXPORTS", "2022-04-07"),
    ("PATANJALI", "2022-04-08"),
    ("VERANDA", "2022-04-11"),
    ("HARIOMPIPE", "2022-04-13"),
    ("CAMPUS", "2022-05-09"),
    ("RAINBOW", "2022-05-10"),
    ("LICI", "2022-05-17"),
    ("PRUDENT", "2022-05-20"),
    ("VENUSPIPES", "2022-05-24"),
    ("DELHIVERY", "2022-05-24"),
    ("PARADEEP", "2022-05-27"),
    ("ETHOSLTD", "2022-05-30"),
    ("EMUDHRA", "2022-06-01"),
    ("AETHER", "2022-06-03"),
    ("SYRMA", "2022-08-26"),
    ("DREAMFOLKS", "2022-09-06"),
    ("TMB", "2022-09-15"),
    ("HARSHA", "2022-09-26"),
    ("EMIL", "2022-10-17"),
    ("TRACXN", "2022-10-20"),
    ("DCXINDIA", "2022-11-11"),
    ("FUSION", "2022-11-15"),
    ("BIKAJI", "2022-11-16"),
    ("MEDANTA", "2022-11-16"),
    ("ACI", "2022-11-21"),
    ("FIVESTAR", "2022-11-21"),
    ("KAYNES", "2022-11-22"),
    ("INOXGREEN", "2022-11-23"),
    ("RUSTOMJEE", "2022-11-24"),
    ("DHARMAJ", "2022-12-08"),
    ("UNIPARTS", "2022-12-12"),
    ("SULA", "2022-12-22"),
    ("LANDMARK", "2022-12-23"),
    ("AHL", "2022-12-23"),
    ("KFINTECH", "2022-12-29"),
    ("ELIN", "2022-12-30"),
    # ── 2023 ────────────────────────────────────────────────────────────────────
    ("RADIANTCMS", "2023-01-04"),
    ("SAH", "2023-01-12"),
    ("DIVGIITTS", "2023-03-14"),
    ("GSLSU", "2023-03-23"),
    ("USK", "2023-04-03"),
    ("AVALON", "2023-04-18"),
    ("MANKIND", "2023-05-09"),
    ("IKIO", "2023-06-16"),
    ("HMAAGRO", "2023-07-04"),
    ("IDEAFORGE", "2023-07-07"),
    ("CYIENTDLM", "2023-07-10"),
    ("SENCO", "2023-07-14"),
    ("UTKARSHBNK", "2023-07-21"),
    ("NETWEB", "2023-07-27"),
    ("YATHARTH", "2023-08-07"),
    ("SBFC", "2023-08-16"),
    ("CONCORDBIO", "2023-08-18"),
    ("TVSSCS", "2023-08-23"),
    ("PYRAMID", "2023-08-29"),
    ("AEROFLEX", "2023-08-31"),
    ("VPRPL", "2023-09-05"),
    ("RATNAVEER", "2023-09-11"),
    ("RISHABH", "2023-09-11"),
    ("JLHL", "2023-09-18"),
    ("RRKABEL", "2023-09-20"),
    ("EMSLIMITED", "2023-09-21"),
    ("SAMHI", "2023-09-22"),
    ("ZAGGLE", "2023-09-22"),
    ("KALAMANDIR", "2023-09-27"),
    ("SIGNATURE", "2023-09-27"),
    ("YATRA", "2023-09-28"),
    ("MVGJL", "2023-10-03"),
    ("JSWINFRA", "2023-10-03"),
    ("UDS", "2023-10-04"),
    ("VALIANTLAB", "2023-10-06"),
    ("PLAZACABLE", "2023-10-12"),
    ("IRMENERGY", "2023-10-26"),
    ("BLUEJET", "2023-11-01"),
    ("CELLO", "2023-11-06"),
    ("HONASA", "2023-11-07"),
    ("ESAFSFB", "2023-11-10"),
    ("ASKAUTOLTD", "2023-11-15"),
    ("IREDA", "2023-11-29"),
    ("GANDHAR", "2023-11-30"),
    ("TATATECH", "2023-11-30"),
    ("FEDFINA", "2023-11-30"),
    ("FLAIR", "2023-12-01"),
    ("DOMS", "2023-12-20"),
    ("INDIASHLTR", "2023-12-20"),
    ("INOXINDIA", "2023-12-21"),
    ("MUTHOOTMF", "2023-12-26"),
    ("SURAJEST", "2023-12-26"),
    ("MOTISONS", "2023-12-26"),
    ("HAPPYFORGE", "2023-12-27"),
    ("MUFTI", "2023-12-27"),
    ("RBZJEWEL", "2023-12-27"),
    ("AZAD", "2023-12-28"),
    ("INNOVACAP", "2023-12-29"),
    # ── 2024 ────────────────────────────────────────────────────────────────────
    ("JYOTICNC", "2024-01-16"),
    ("MEDIASSIST", "2024-01-23"),
    ("EPACK", "2024-01-30"),
    ("NOVAAGRI", "2024-01-31"),
    ("BLSE", "2024-02-06"),
    ("PARKHOTELS", "2024-02-12"),
    ("CAPITALSFB", "2024-02-14"),
    ("JSFB", "2024-02-14"),
    ("RPTECH", "2024-02-14"),
    ("ENTERO", "2024-02-16"),
    ("VSTL", "2024-02-20"),
    ("JUNIPER", "2024-02-28"),
    ("GPTHEALTH", "2024-02-29"),
    ("PLATIND", "2024-03-05"),
    ("EXICOM", "2024-03-05"),
    ("MUKKA", "2024-03-07"),
    ("RKSWAMY", "2024-03-12"),
    ("JGCHEM", "2024-03-13"),
    ("GOPAL", "2024-03-14"),
    ("PVSL", "2024-03-19"),
    ("KRYSTAL", "2024-03-21"),
    ("SRM", "2024-04-03"),
    ("BHARTIHEXA", "2024-04-12"),
    ("IDEA", "2024-04-25"),
    ("JNKINDIA", "2024-04-30"),
    ("INDGN", "2024-05-13"),
    ("AADHARHFC", "2024-05-15"),
    ("TBOTEK", "2024-05-15"),
    ("GODIGIT", "2024-05-23"),
    ("AWFIS", "2024-05-30"),
    ("KRONOX", "2024-06-10"),
    ("IXIGO", "2024-06-18"),
    ("DEEDEV", "2024-06-26"),
    ("AFIL", "2024-06-26"),
    ("STANLEY", "2024-06-28"),
    ("ABDL", "2024-07-02"),
    ("VRAJ", "2024-07-03"),
    ("BANSALWIRE", "2024-07-10"),
    ("EMCURE", "2024-07-10"),
    ("SANSTAR", "2024-07-26"),
    ("AKUMS", "2024-08-06"),
    ("CEIGALL", "2024-08-08"),
    ("OLAELEC", "2024-08-09"),
    ("UNIECOM", "2024-08-13"),
    ("FIRSTCRY", "2024-08-13"),
    ("SSDL", "2024-08-20"),
    ("INTERARCH", "2024-08-26"),
    ("ORIENTTECH", "2024-08-28"),
    ("PREMIERENE", "2024-09-03"),
    ("ECOSMOBLTY", "2024-09-04"),
    ("STYLEBAAZA", "2024-09-06"),
    ("GALAPREC", "2024-09-09"),
    ("BALAJEE", "2024-09-12"),
    ("TOLINS", "2024-09-16"),
    ("BAJAJHFL", "2024-09-16"),
    ("KROSS", "2024-09-16"),
    ("PNGJL", "2024-09-17"),
    ("ARKADE", "2024-09-24"),
    ("WCIL", "2024-09-24"),
    ("NORTHARC", "2024-09-24"),
    ("MANBA", "2024-09-30"),
    ("KRN", "2024-10-03"),
    ("DIFFNKG", "2024-10-04"),
    ("GARUDA", "2024-10-15"),
    ("HYUNDAI", "2024-10-22"),
    ("WAAREEENER", "2024-10-28"),
    ("DBEIL", "2024-10-28"),
    ("GODAVARIB", "2024-10-30"),
    ("AFCONS", "2024-11-04"),
    ("SAGILITY", "2024-11-12"),
    ("SWIGGY", "2024-11-13"),
    ("ACMESOLAR", "2024-11-13"),
    ("NIVABUPA", "2024-11-14"),
    ("BLACKBUCK", "2024-11-22"),
    ("NTPCGREEN", "2024-11-27"),
    ("EIEL", "2024-11-29"),
    ("SURAKSHA", "2024-12-06"),
    ("SAILIFE", "2024-12-18"),
    ("VMM", "2024-12-18"),
    ("MOBIKWIK", "2024-12-18"),
    ("IGIL", "2024-12-19"),
    ("IKS", "2024-12-19"),
    ("MAMATA", "2024-12-27"),
    ("DAMCAPITAL", "2024-12-27"),
    ("SANATHAN", "2024-12-27"),
    ("CEWATER", "2024-12-27"),
    ("TRANSRAILL", "2024-12-27"),
    ("VENTIVE", "2024-12-30"),
    ("SENORES", "2024-12-30"),
    ("CARRARO", "2024-12-30"),
    ("UNIMECH", "2024-12-31"),
    # ── 2025 ────────────────────────────────────────────────────────────────────
    ("INDOFARM", "2025-01-07"),
    ("SGLTL", "2025-01-13"),
    ("QUADFUTURE", "2025-01-14"),
    ("LAXMIDENTL", "2025-01-20"),
    ("STALLION", "2025-01-23"),
    ("DENTA", "2025-01-29"),
    ("AGARWALEYE", "2025-02-04"),
    ("AJAXENGG", "2025-02-17"),
    ("HEXT", "2025-02-19"),
    ("QPOWER", "2025-02-25"),
    ("ATHERENERG", "2025-05-06"),
    ("BORANA", "2025-05-27"),
    ("BELRISE", "2025-05-28"),
    ("THELEELA", "2025-06-02"),
    ("AEGISVOPAK", "2025-06-02"),
    ("PROSTARM", "2025-06-03"),
    ("SCODATUBES", "2025-06-04"),
    ("OSWALPUMPS", "2025-06-20"),
    ("ARISINFRA", "2025-06-25"),
    ("GLOBECIVIL", "2025-07-01"),
    ("ELLEN", "2025-07-01"),
    ("KALPATARU", "2025-07-01"),
    ("HDBFS", "2025-07-02"),
    ("SAMBHV", "2025-07-02"),
    ("IGCL", "2025-07-03"),
    ("CRIZAC", "2025-07-09"),
    ("TRAVELFOOD", "2025-07-10"),
    ("SMARTWORKS", "2025-07-17"),
    ("ANTHEM", "2025-07-21"),
    ("INDIQUBE", "2025-07-30"),
    ("EBGNG", "2025-07-30"),
    ("BRIGHOTEL", "2025-07-31"),
    ("SHANTIGOLD", "2025-08-01"),
    ("CPPLUS", "2025-08-05"),
    ("LAXMIINDIA", "2025-08-05"),
    ("MBEL", "2025-08-06"),
    ("LOTUSDEV", "2025-08-06"),
    ("HILINFRA", "2025-08-12"),
    ("ALLTIME", "2025-08-14"),
    ("JSWCEMENT", "2025-08-14"),
    ("BLUESTONE", "2025-08-19"),
    ("REGAAL", "2025-08-20"),
    ("VIKRAMSOLR", "2025-08-26"),
    ("GEMAROMA", "2025-08-26"),
    ("SHREEJISPG", "2025-08-26"),
    ("PATELRMART", "2025-08-26"),
    ("MEIL", "2025-08-28"),
    ("AHCL", "2025-09-03"),
    ("VIKRAN", "2025-09-03"),
    ("AMANTA", "2025-09-08"),
    ("SHRINGARMS", "2025-09-17"),
    ("DEVX", "2025-09-17"),
    ("URBANCO", "2025-09-17"),
    ("EUROPRATIK", "2025-09-23"),
    ("IVALUE", "2025-09-25"),
    ("GKENERGY", "2025-09-26"),
    ("SAATVIKGL", "2025-09-26"),
    ("GANESHCP", "2025-09-29"),
    ("ATLANTAELE", "2025-09-29"),
    ("JARO", "2025-09-30"),
    ("SOLARWORLD", "2025-09-30"),
    ("ARSSBL", "2025-09-30"),
    ("STYL", "2025-09-30"),
    ("EPACKPEB", "2025-10-01"),
    ("JAINREC", "2025-10-01"),
    ("TRUALT", "2025-10-03"),
    ("JKIPL", "2025-10-03"),
    ("PACEDIGITK", "2025-10-06"),
    ("GLOTTIS", "2025-10-07"),
    ("OMFR", "2025-10-08"),
    ("ADVANCE", "2025-10-08"),
    ("WEWORK", "2025-10-10"),
    ("TATACAP", "2025-10-13"),
    ("LGEINDIA", "2025-10-14"),
    ("RUBICON", "2025-10-16"),
    ("CRAMC", "2025-10-16"),
    ("CANHLIFE", "2025-10-17"),
    ("MIDWESTLTD", "2025-10-24"),
    ("ORKLAINDIA", "2025-11-06"),
    ("STUDDS", "2025-11-07"),
    ("LENSKART", "2025-11-10"),
    ("GROWW", "2025-11-12"),
    ("PINELABS", "2025-11-14"),
    ("PWL", "2025-11-18"),
    ("EMMVEE", "2025-11-18"),
    ("TENNIND", "2025-11-19"),
    ("UTLSOLAR", "2025-11-20"),
    ("CAPILLARY", "2025-11-21"),
    ("EXCELSOFT", "2025-11-26"),
    ("SUDEEPPHRM", "2025-11-28"),
    ("VIDYAWIRES", "2025-12-10"),
    ("MEESHO", "2025-12-10"),
    ("AEQUS", "2025-12-10"),
    ("CORONA", "2025-12-15"),
    ("WAKEFIT", "2025-12-15"),
    ("PARKHOSPS", "2025-12-17"),
    ("NEPHROPLUS", "2025-12-17"),
    ("ICICIAMC", "2025-12-19"),
    ("KSHINTL", "2025-12-23"),
    ("GKSL", "2025-12-30"),
    # ── 2026 ────────────────────────────────────────────────────────────────────
    ("BHARATCOAL", "2026-01-16"),
    ("AMAGI", "2026-01-21"),
    ("SHADOWFAX", "2026-01-28"),
    ("AYE", "2026-02-16"),
    ("FRACTAL", "2026-02-16"),
    ("GAUDIUMIVF", "2026-02-27"),
    ("SRTL", "2026-03-02"),
    ("CLEANMAX", "2026-03-02"),
    ("PNGSREVA", "2026-03-04"),
    ("OMNI", "2026-03-05"),
    ("SEDEMAC", "2026-03-11"),
    ("RSL", "2026-03-16"),
    ("INNOVISION", "2026-03-20"),
    ("GSPCROP", "2026-03-24"),
    ("CMPDI", "2026-03-27"),
    ("AMIRCHAND", "2026-04-02"),
    ("POWERICA", "2026-04-02"),
    ("SAIPARENT", "2026-04-02"),
    ("OMPOWER", "2026-04-17"),
    ("KISSHT", "2026-05-08"),
    ("CMRGREEN", "2026-06-10"),
    ("HEXAGON", "2026-06-12"),
]

# ═══════════════════════════════════════════════════════════════════════════════
# NSE symbol → Yahoo Finance ticker overrides
# STATIC_IPOS now uses the actual NSE trading symbols sourced from ipoplatform,
# so no overrides are needed — Yahoo Finance finds them as SYMBOL.NS directly.
# ═══════════════════════════════════════════════════════════════════════════════
NSE_TO_YF: dict[str, str] = {}

# Symbols to fetch via NSE bhavcopy (not available on Yahoo Finance).
# Using actual NSE trading symbols — no secondary remapping needed.
NSE_BHAV_SYMBOLS = {
    "BARBEQUE", "ZOMATO", "GLS",
    "AMIORG", "FIRSTCRY", "BLACKBUCK", "MANBA",
}

# No remapping needed: STATIC_IPOS now uses the correct NSE bhavcopy symbols directly.
BHAV_SYMBOL_MAP: dict[str, str] = {}

# In-memory cache: symbol -> pd.DataFrame with columns [date, high, low, close]
_BHAV_CACHE: dict[str, pd.DataFrame] = {}

_NSE_BHAV_URL = (
    "https://archives.nseindia.com/products/content/sec_bhavdata_full_{date_str}.csv"
)


def _bhav_fetch_one_day(dt: pd.Timestamp, symbols: set[str]) -> dict[str, dict]:
    """
    Download one day's NSE bhavcopy and return {orig_symbol: {date,high,low,close}}.
    Uses BHAV_SYMBOL_MAP to translate renamed/IPO-era tickers back to original symbols.
    """
    date_str = dt.strftime("%d%m%Y")
    url = _NSE_BHAV_URL.format(date_str=date_str)
    # Build reverse map: bhav_sym → orig_sym for this batch
    bhav_to_orig: dict[str, str] = {}
    for orig in symbols:
        bhav_to_orig[BHAV_SYMBOL_MAP.get(orig, orig)] = orig

    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=20)
            if r.status_code != 200 or "csv" not in r.headers.get("Content-Type", ""):
                return {}
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = df.columns.str.strip()
            df["SYMBOL"] = df["SYMBOL"].str.strip()
            df["SERIES"] = df["SERIES"].str.strip()
            # Filter: equity series, our bhavcopy symbols
            df = df[
                (df["SERIES"] == "EQ") &
                (df["SYMBOL"].isin(bhav_to_orig.keys()))
            ]
            out = {}
            for _, row in df.iterrows():
                bhav_sym  = str(row["SYMBOL"])
                orig_sym  = bhav_to_orig.get(bhav_sym, bhav_sym)
                out[orig_sym] = {
                    "date":  dt,
                    "high":  float(row["HIGH_PRICE"]),
                    "low":   float(row["LOW_PRICE"]),
                    "close": float(row["CLOSE_PRICE"]),
                }
            return out
        except Exception:
            if attempt < 2:
                time.sleep(1)
    return {}


def prefetch_bhav(ipos_with_dates: list[tuple[str, date]]) -> None:
    """
    Pre-download NSE bhavcopy for every symbol in NSE_BHAV_SYMBOLS that
    appears in ipos_with_dates. Populates _BHAV_CACHE.
    """
    global _BHAV_CACHE

    # Build per-symbol date ranges
    sym_ranges: dict[str, tuple[date, date]] = {}
    for sym, ld in ipos_with_dates:
        if sym not in NSE_BHAV_SYMBOLS:
            continue
        anniv   = add_one_year(ld)
        end_dt  = min(anniv + timedelta(days=15), TODAY)
        sym_ranges[sym] = (ld, end_dt)

    if not sym_ranges:
        return

    # Union of all dates we need
    all_start = min(v[0] for v in sym_ranges.values())
    all_end   = max(v[1] for v in sym_ranges.values())
    business_days = pd.bdate_range(start=all_start, end=all_end)

    symbols_needed = set(sym_ranges.keys())
    print(
        f"\n[BHAV] Pre-fetching NSE bhavcopy for {len(symbols_needed)} symbols "
        f"({len(business_days)} trading days) …"
    )

    # Per-symbol accumulator
    rows: dict[str, list[dict]] = {s: [] for s in symbols_needed}

    def fetch_and_collect(dt: pd.Timestamp) -> None:
        day_data = _bhav_fetch_one_day(dt, symbols_needed)
        for sym, row in day_data.items():
            rows[sym].append(row)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(fetch_and_collect, dt): dt for dt in business_days}
        done = 0
        for _ in as_completed(futures):
            done += 1
            if done % 50 == 0:
                print(f"[BHAV] Downloaded {done}/{len(business_days)} days …")

    # Build DataFrames, filter to each symbol's window, store in cache
    for sym, row_list in rows.items():
        if not row_list:
            continue
        df = (
            pd.DataFrame(row_list)
            .sort_values("date")
            .reset_index(drop=True)
        )
        # Clip to the symbol's own date range
        s_start, s_end = sym_ranges[sym]
        df = df[
            (df["date"].dt.date >= s_start) & (df["date"].dt.date <= s_end)
        ].reset_index(drop=True)
        _BHAV_CACHE[sym] = df
        print(f"[BHAV] {sym}: {len(df)} bars cached.")


def add_one_year(d: date) -> date:
    try:
        return d.replace(year=d.year + 1)
    except ValueError:          # Feb 29 edge case
        return d.replace(year=d.year + 1, day=28)


def _fetch_yf_ticker(ticker: str, start: date, end: date, retries: int = 3) -> pd.DataFrame:
    """Fetch daily OHLC for a fully-qualified Yahoo Finance ticker (e.g. ZOMATO.NS)."""
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


def fetch_ohlc(symbol: str, start: date, end: date, retries: int = 3) -> pd.DataFrame:
    """Return daily OHLC: checks bhavcopy cache first, then Yahoo Finance."""
    # 1. Check pre-fetched bhavcopy cache (for symbols absent from Yahoo Finance)
    if symbol in _BHAV_CACHE:
        df = _BHAV_CACHE[symbol]
        return df[
            (df["date"].dt.date >= start) & (df["date"].dt.date <= end)
        ].reset_index(drop=True)

    # 2. Yahoo Finance — try corrected ticker then .NS, fallback .BO
    yf_base = NSE_TO_YF.get(symbol, symbol)
    df = _fetch_yf_ticker(yf_base + ".NS", start, end, retries)
    if not df.empty:
        return df
    return _fetch_yf_ticker(yf_base + ".BO", start, end, retries)


# ═══════════════════════════════════════════════════════════════════════════════
# Stop-loss modes
#   "fixed"    – hard stop at entry × 0.90  (original baseline)
#   "trailing" – stop = max(stop, close × 0.90) updated daily
#   "atr"      – stop = entry − 2 × ATR14 computed on entry day
#   "time"     – fixed stop PLUS exit at close if still underwater after 30 days
STOP_MODE: str = "fixed"

# Exit modes (all use STOP_MODE stop-loss)
#   "anniversary" – exit at 1-year close (baseline)
#   "target40"    – exit when high >= entry × 1.40
#   "target60"    – exit when high >= entry × 1.60
#   "partial30"   – sell 50% when high >= entry × 1.30, hold rest to anniversary
#   "nifty_crash" – exit at close when Nifty 500 drops >10% from peak since entry
EXIT_MODE: str = "anniversary"

# Re-entry modes (all use stop_mode=fixed, exit_mode=anniversary unless noted)
#   "unlimited"     – no cap, no cooling, always 10% threshold (baseline)
#   "cap2"          – max 2 entries per IPO year window
#   "cap3"          – max 3 entries per IPO year window
#   "cool10"        – 10 trading-day cooling period after each stop
#   "rising_thresh" – 10% for entry 1, 15% for entry 2, 20% for entry 3+
REENTRY_MODE: str = "unlimited"

# Entry-filter modes (minimise losers)
#   "none"         – no filters, baseline
#   "early"        – only enter within first 180 days of listing
#   "entry1"       – only first entry per IPO (cap1)
#   "regime"       – only enter when NIFTYBEES > its 50-day SMA
#   "bullcandle"   – entry day close must be in upper 50% of day range
#   "combo"        – early + entry1 + regime combined
FILTER_MODE: str = "none"

# Tighter-stop modes (reduce loss magnitude)
#   "s10" – 10% stop (baseline)
#   "s7"  – 7% stop
#   "s5"  – 5% stop
STOP_PCT: float = 0.10

_NIFTYBEES_SMA: dict = {}   # date → 50-day SMA of NIFTYBEES close

def _load_niftybees_sma() -> None:
    global _NIFTYBEES_SMA
    if _NIFTYBEES_SMA:
        return
    df = _fetch_yf_ticker("NIFTYBEES.NS", date(2018, 1, 1), TODAY)
    if df.empty:
        print("  [warn] NIFTYBEES data unavailable — regime filter disabled")
        return
    df = df.sort_values("date").reset_index(drop=True)
    df["sma50"] = df["close"].rolling(50, min_periods=20).mean()
    for _, row in df.iterrows():
        if not pd.isna(row["sma50"]):
            _NIFTYBEES_SMA[row["date"].date()] = float(row["sma50"]) < float(row["close"])
    print(f"  NIFTYBEES 50-SMA regime filter ready: {len(_NIFTYBEES_SMA)} days")


_NIFTY500: dict = {}   # empty until loaded by _load_nifty500()
_NIFTY500_TRIED: bool = False


def _load_nifty500() -> None:
    global _NIFTY500, _NIFTY500_TRIED
    if _NIFTY500_TRIED:
        return
    _NIFTY500_TRIED = True
    # Try Nifty 500 index first, fall back to Nifty 50 ETF as broad-market proxy
    for ticker in ("^CNX500", "NIFTYBEES.NS", "^NSEI"):
        df = _fetch_yf_ticker(ticker, date(2019, 1, 1), TODAY)
        if not df.empty:
            for _, row in df.iterrows():
                _NIFTY500[row["date"].date()] = float(row["close"])
            print(f"  Nifty broad-market index loaded ({ticker}): {len(_NIFTY500)} days")
            return
    print("  [warn] Nifty 500/50 data unavailable — crash-exit mode falls back to anniversary")



def _atr14(df, idx: int) -> float:
    """14-day ATR ending at row idx."""
    window = df.iloc[max(0, idx - 14): idx + 1]
    if len(window) < 2:
        return float("nan")
    highs  = window["high"].values.astype(float)
    lows   = window["low"].values.astype(float)
    closes = window["close"].values.astype(float)
    tr = []
    for j in range(1, len(window)):
        tr.append(max(highs[j] - lows[j],
                      abs(highs[j] - closes[j - 1]),
                      abs(lows[j]  - closes[j - 1])))
    return float(np.mean(tr)) if tr else float("nan")


def backtest_one(symbol: str, listing_date, df,
                 stop_mode: str = STOP_MODE,
                 exit_mode: str = EXIT_MODE,
                 reentry_mode: str = REENTRY_MODE,
                 filter_mode: str = FILTER_MODE,
                 stop_pct: float = STOP_PCT) -> list:
    """
    IPO Reversal rules with configurable entry filters and stop %.
    stop_mode    : fixed | trailing | atr | time
    exit_mode    : anniversary | target40 | target60 | partial30 | nifty_crash
    reentry_mode : unlimited | cap2 | cap3 | cool10 | rising_thresh
    filter_mode  : none | early | entry1 | regime | bullcandle | combo
    stop_pct     : 0.10 / 0.07 / 0.05
    """
    base = {"symbol": symbol, "listing_date": listing_date}

    if df.empty:
        return [{**base, "status": "no_data"}]

    anniversary = add_one_year(listing_date)
    df = df[df["date"].dt.date >= listing_date].copy().reset_index(drop=True)

    if len(df) < 3:
        return [{**base, "status": "no_data"}]

    if exit_mode == "nifty_crash" and not _NIFTY500_TRIED:
        _load_nifty500()

    if filter_mode in ("regime", "combo") and not _NIFTYBEES_SMA:
        _load_niftybees_sma()

    # entry1 = only allow 1 entry per IPO (cap1 via filter_mode)
    entry_cap = 1 if filter_mode in ("entry1", "combo") else 9999

    trades:       list = []
    trailing_low        = float("inf")
    scan_from           = 0
    entry_num           = 0

    while scan_from < len(df):
        # ── Entry cap checks (reentry_mode + filter_mode entry1/combo) ───────
        if reentry_mode == "cap2" and entry_num >= 2:
            break
        if reentry_mode == "cap3" and entry_num >= 3:
            break
        if entry_num >= entry_cap:
            break

        # ── Phase 1: find next entry trigger ────────────────────────────────
        entry_idx  = None
        entry_date = entry_price = hard_stop = None

        # Rising threshold: tighter for subsequent re-entries
        if reentry_mode == "rising_thresh":
            bounce_mult = 1.10 if entry_num == 0 else (1.15 if entry_num == 1 else 1.20)
        else:
            bounce_mult = 1.10

        for i in range(scan_from, len(df)):
            row = df.iloc[i]
            d   = row["date"].date()
            if d >= anniversary:
                break
            trailing_low = min(trailing_low, float(row["low"]))
            if float(row["high"]) >= trailing_low * bounce_mult:
                # ── Entry filters ────────────────────────────────────────────
                skip = False
                # early: only within first 180 days of listing
                if filter_mode in ("early", "combo"):
                    if (d - listing_date).days > 180:
                        skip = True
                # regime: NIFTYBEES above 50-SMA on entry day
                if not skip and filter_mode in ("regime", "combo"):
                    above = _NIFTYBEES_SMA.get(d, True)   # default True if no data
                    if not above:
                        skip = True
                # bullcandle: close in upper 50% of day's high-low range
                if not skip and filter_mode in ("bullcandle", "combo"):
                    hi_d  = float(row["high"])
                    lo_d  = float(row["low"])
                    cl_d  = float(row["close"])
                    rng   = hi_d - lo_d
                    if rng > 0 and (cl_d - lo_d) / rng < 0.50:
                        skip = True
                if skip:
                    # Update trailing_low and continue scanning
                    continue
                entry_idx   = i
                entry_date  = d
                entry_price = float(row["close"])
                if stop_mode == "atr":
                    atr = _atr14(df, i)
                    hard_stop = (entry_price - 2 * atr) if not np.isnan(atr) else entry_price * (1 - stop_pct)
                else:
                    hard_stop = entry_price * (1 - stop_pct)
                break

        if entry_idx is None:
            break

        entry_num     += 1
        days_to_entry  = (entry_date - listing_date).days
        current_stop   = hard_stop

        # Partial-exit state
        partial_done       = False
        partial_leg1_price = None

        # Nifty-crash: track peak from entry day onward
        nifty_peak = _NIFTY500.get(entry_date, 0.0)

        # ── Phase 2: hold until stop / target / crash / anniversary ──────────
        exited = False
        for i in range(entry_idx + 1, len(df)):
            row       = df.iloc[i]
            d         = row["date"].date()
            lo        = float(row["low"])
            hi        = float(row["high"])
            cl        = float(row["close"])
            days_held = (d - entry_date).days

            # Update trailing stop
            if stop_mode == "trailing":
                current_stop = max(current_stop, cl * 0.90)

            # Time-based exit (fixed stop + 30d no-progress)
            if stop_mode == "time" and days_held >= 30 and cl <= entry_price:
                ret = cl / entry_price - 1
                trades.append({**base,
                    "entry_num": entry_num, "status": "time_exit",
                    "entry_date": entry_date, "entry_price": round(entry_price, 2),
                    "stop_price": round(current_stop, 2),
                    "exit_date": d, "exit_price": round(cl, 2),
                    "return_pct": round(ret * 100, 2),
                    "days_to_entry": days_to_entry, "days_held": days_held,
                })
                trailing_low = float("inf")
                scan_from    = i + 10 if reentry_mode == "cool10" else i
                exited = True; break

            # ── Profit-target exits ──────────────────────────────────────────
            if exit_mode in ("target40", "target60"):
                tgt_pct   = 0.40 if exit_mode == "target40" else 0.60
                tgt_price = entry_price * (1 + tgt_pct)
                if hi >= tgt_price:
                    trades.append({**base,
                        "entry_num": entry_num, "status": "target_exit",
                        "entry_date": entry_date, "entry_price": round(entry_price, 2),
                        "exit_date": d, "exit_price": round(tgt_price, 2),
                        "return_pct": round(tgt_pct * 100, 2),
                        "days_to_entry": days_to_entry, "days_held": days_held,
                    })
                    trailing_low = float("inf")
                    scan_from    = i + 10 if reentry_mode == "cool10" else i
                    exited = True; break

            # ── Partial exit – first leg at +30% ────────────────────────────
            if exit_mode == "partial30" and not partial_done:
                if hi >= entry_price * 1.30:
                    partial_done       = True
                    partial_leg1_price = entry_price * 1.30

            # ── Stop-loss check ──────────────────────────────────────────────
            if lo <= current_stop:
                exit_px = current_stop
                if exit_mode == "partial30" and partial_done:
                    # blended: 50% locked at +30%, 50% stopped out
                    leg2_ret = exit_px / entry_price - 1
                    ret      = 0.5 * 0.30 + 0.5 * leg2_ret
                    status   = "partial_stop"
                else:
                    ret    = exit_px / entry_price - 1
                    status = "stop_hit"
                trades.append({**base,
                    "entry_num": entry_num, "status": status,
                    "entry_date": entry_date, "entry_price": round(entry_price, 2),
                    "stop_price": round(current_stop, 2),
                    "exit_date": d, "exit_price": round(exit_px, 2),
                    "return_pct": round(ret * 100, 2),
                    "days_to_entry": days_to_entry, "days_held": days_held,
                })
                trailing_low = float("inf")
                scan_from    = i + 10 if reentry_mode == "cool10" else i
                exited = True; break

            # ── Nifty 500 crash exit ─────────────────────────────────────────
            if exit_mode == "nifty_crash" and _NIFTY500:
                nd = _NIFTY500.get(d, 0.0)
                if nd > 0:
                    nifty_peak = max(nifty_peak, nd)
                    if nifty_peak > 0 and nd < nifty_peak * 0.90:
                        ret = cl / entry_price - 1
                        trades.append({**base,
                            "entry_num": entry_num, "status": "crash_exit",
                            "entry_date": entry_date, "entry_price": round(entry_price, 2),
                            "exit_date": d, "exit_price": round(cl, 2),
                            "return_pct": round(ret * 100, 2),
                            "days_to_entry": days_to_entry, "days_held": days_held,
                        })
                        trailing_low = float("inf")
                        scan_from    = i + 10 if reentry_mode == "cool10" else i
                        exited = True; break

            # ── Anniversary exit ─────────────────────────────────────────────
            if d >= anniversary:
                if exit_mode == "partial30" and partial_done:
                    leg2_ret = cl / entry_price - 1
                    ret      = 0.5 * 0.30 + 0.5 * leg2_ret
                    status   = "partial_anniversary"
                else:
                    ret    = cl / entry_price - 1
                    status = "survived_positive" if ret > 0 else "survived_negative"
                trades.append({**base,
                    "entry_num": entry_num, "status": status,
                    "entry_date": entry_date, "entry_price": round(entry_price, 2),
                    "exit_date": d, "exit_price": round(cl, 2),
                    "return_pct": round(ret * 100, 2),
                    "days_to_entry": days_to_entry, "days_held": days_held,
                })
                scan_from = len(df); exited = True; break

        if not exited:
            last    = df.iloc[-1]
            last_cl = float(last["close"])
            unreal  = last_cl / entry_price - 1
            trades.append({**base,
                "entry_num": entry_num, "status": "active",
                "entry_date": entry_date, "entry_price": round(entry_price, 2),
                "last_date": last["date"].date(), "last_price": round(last_cl, 2),
                "return_pct": round(unreal * 100, 2),
                "days_to_entry": days_to_entry,
                "days_held": (last["date"].date() - entry_date).days,
            })
            break

    if not trades:
        last_d = df["date"].dt.date.iloc[-1]
        return [{**base, "status": "no_trigger",
                 "days_observed": (last_d - listing_date).days}]
    return trades


def _summarise(all_trades: list, mode_label: str) -> dict:
    """Compute summary statistics for one mode's trade list."""
    df_all    = pd.DataFrame(all_trades)
    WIN_STATUSES  = {"survived_positive", "target_exit", "partial_anniversary",
                     "partial_stop"}
    DONE_STATUSES = {"stop_hit", "time_exit", "survived_positive",
                     "survived_negative", "target_exit", "crash_exit",
                     "partial_anniversary", "partial_stop"}
    completed = df_all[df_all["status"].isin(DONE_STATUSES)]
    winners   = completed[completed["return_pct"] > 0]
    n         = len(completed)
    if n == 0:
        return {"mode": mode_label, "trades": 0}
    avg_ent = (df_all.groupby(["symbol", "listing_date"])["entry_num"].max().mean()
               if "entry_num" in df_all.columns else float("nan"))
    return {
        "mode":       mode_label,
        "trades":     n,
        "win_rate":   len(winners) / n * 100,
        "mean_ret":   completed["return_pct"].mean(),
        "median_ret": completed["return_pct"].median(),
        "best":       completed["return_pct"].max(),
        "worst":      completed["return_pct"].min(),
        "avg_days":   completed["days_held"].mean(),
        "avg_entries": avg_ent,
    }


def _run(label, ipos, data_cache, **kwargs) -> dict:
    all_trades = []
    for sym, ld_str in ipos:
        ld = datetime.strptime(ld_str, "%Y-%m-%d").date()
        df = data_cache.get((sym, ld_str), pd.DataFrame())
        all_trades.extend(backtest_one(sym, ld, df, **kwargs))
    r = _summarise(all_trades, label)
    # Also compute stop-hit rate and avg loss
    dft = pd.DataFrame(all_trades)
    stops = dft[dft["status"] == "stop_hit"]
    r["stop_rate"]  = len(stops) / max(len(dft[dft["status"].isin(
        {"stop_hit","survived_positive","survived_negative",
         "target_exit","crash_exit","partial_anniversary","partial_stop"})]), 1) * 100
    r["avg_loss"]   = stops["return_pct"].mean() if len(stops) else 0.0
    r["total_rows"] = len(all_trades)
    return r


def main():
    ipos  = STATIC_IPOS
    total = len(ipos)

    ipos_dates = [(sym, datetime.strptime(ld_str, "%Y-%m-%d").date()) for sym, ld_str in ipos]
    prefetch_bhav(ipos_dates)

    print(f"\n{'═'*70}")
    print(f"  IPO REVERSAL — MINIMISING LOSERS  (Opt #5)")
    print(f"  Universe : NSE Mainboard IPOs FY20-FY27  ({total} names)")
    print(f"  Run date : {TODAY}")
    print(f"  Part A: Entry filters    (fixed 10% stop + anniversary + unlimited re-entry)")
    print(f"  Part B: Tighter stop %   (no entry filter + anniversary + unlimited re-entry)")
    print(f"{'═'*70}\n")

    # ── Fetch OHLC data once ──────────────────────────────────────────────────
    print("  Fetching OHLC data …")
    data_cache: dict = {}
    for idx, (sym, ld_str) in enumerate(ipos, 1):
        ld     = datetime.strptime(ld_str, "%Y-%m-%d").date()
        anniv  = add_one_year(ld)
        end_dt = min(anniv + timedelta(days=15), TODAY)
        data_cache[(sym, ld_str)] = fetch_ohlc(sym, ld, end_dt)
        if idx % 50 == 0:
            print(f"    {idx}/{total} fetched …")
        time.sleep(0.12)
    print(f"  Data fetch complete.\n")

    # Pre-load NIFTYBEES SMA for regime filter
    _load_niftybees_sma()

    # ── PART A: Entry filter comparison ──────────────────────────────────────
    filter_configs = [
        ("baseline",    dict(filter_mode="none",       stop_pct=0.10)),
        ("early_180d",  dict(filter_mode="early",      stop_pct=0.10)),
        ("entry1_only", dict(filter_mode="entry1",     stop_pct=0.10)),
        ("regime_nifty",dict(filter_mode="regime",     stop_pct=0.10)),
        ("bullcandle",  dict(filter_mode="bullcandle", stop_pct=0.10)),
        ("combo",       dict(filter_mode="combo",      stop_pct=0.10)),
    ]

    print("  Running Part A: entry filters …")
    filter_results = [_run(label, ipos, data_cache, **kw) for label, kw in filter_configs]

    # ── PART B: Tighter stop comparison ──────────────────────────────────────
    stop_configs = [
        ("stop_10pct", dict(filter_mode="none", stop_pct=0.10)),
        ("stop_7pct",  dict(filter_mode="none", stop_pct=0.07)),
        ("stop_5pct",  dict(filter_mode="none", stop_pct=0.05)),
    ]

    print("  Running Part B: tighter stops …")
    stop_results = [_run(label, ipos, data_cache, **kw) for label, kw in stop_configs]

    def print_table(results, title):
        print(f"\n{'═'*88}")
        print(f"  {title}")
        print(f"{'─'*88}")
        print(f"  {'Label':<16} {'Trades':>7} {'Win%':>7} {'StopRate':>9} "
              f"{'AvgLoss':>8} {'MeanRet':>9} {'Best':>8} {'AvgDays':>8}")
        print(f"{'─'*88}")
        for r in results:
            if r["trades"] == 0:
                print(f"  {r['mode']:<16}  no trades"); continue
            print(f"  {r['mode']:<16} {r['trades']:>7} {r['win_rate']:>6.1f}% "
                  f"{r['stop_rate']:>8.1f}% {r['avg_loss']:>+7.1f}% "
                  f"{r['mean_ret']:>+8.1f}% {r['best']:>+7.1f}% "
                  f"{r['avg_days']:>7.0f}d")
        print(f"{'═'*88}")

    print_table(filter_results,
        "PART A — Entry Filters  (StopRate = % of completed trades stopped out)")
    print_table(stop_results,
        "PART B — Tighter Stop %  (reduces loss magnitude per stopped trade)")

    print(f"\n  Legend (Part A):")
    print(f"  baseline     = no filters")
    print(f"  early_180d   = only enter within first 180 days of listing")
    print(f"  entry1_only  = only take the first entry signal per IPO")
    print(f"  regime_nifty = only enter when NIFTYBEES > 50-day SMA (bull market)")
    print(f"  bullcandle   = only enter when close is in upper 50% of day's range")
    print(f"  combo        = early + entry1 + regime combined")
    print(f"\n  Legend (Part B):")
    print(f"  stop_10pct   = hard stop 10% below entry (baseline)")
    print(f"  stop_7pct    = hard stop 7% below entry")
    print(f"  stop_5pct    = hard stop 5% below entry")

    # ── Save baseline trades ──────────────────────────────────────────────────
    all_base = []
    for sym, ld_str in ipos:
        ld = datetime.strptime(ld_str, "%Y-%m-%d").date()
        df = data_cache.get((sym, ld_str), pd.DataFrame())
        all_base.extend(backtest_one(sym, ld, df))
    pd.DataFrame(all_base).to_csv("ipo_reversal_results.csv", index=False)
    print(f"\n  Baseline trades saved → ipo_reversal_results.csv")
    print(f"{'═'*70}\n")


if __name__ == "__main__":
    main()
