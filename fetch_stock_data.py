"""
Fetch live NSE stock data from the internet and update ALL_DATA.csv
so the Streamlit dashboard reflects current prices.

Data sources tried in order:
  1. Yahoo Finance REST API  (no key required)
  2. NSE India unofficial REST API  (no key required)

Usage:
    python fetch_stock_data.py              # single fetch
    python fetch_stock_data.py --loop 30   # refresh every 30 seconds
    python fetch_stock_data.py --source nse  # force NSE India source
"""

import argparse
import logging
import os
import time
from datetime import datetime

import pandas as pd
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)

ALL_DATA_CSV = "ALL_DATA.csv"
ORIGINAL_CSV = "ALL_DATA_original.csv"
SPREAD_PCT = 0.001  # 0.1 % spread used to estimate bid/ask from LTP

# Trust the proxy CA bundle so HTTPS works inside the cloud sandbox
_CA_BUNDLE = os.environ.get("REQUESTS_CA_BUNDLE") or "/root/.ccr/ca-bundle.crt"
_VERIFY = _CA_BUNDLE if os.path.exists(_CA_BUNDLE) else True

_COMMON_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ---------------------------------------------------------------------------
# Source 1 – Yahoo Finance REST API  (no library dependency beyond requests)
# ---------------------------------------------------------------------------

_YF_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"


def _yf_price(session: requests.Session, symbol: str) -> float:
    """Fetch latest price for one NSE symbol from Yahoo Finance."""
    ticker = symbol + ".NS"
    try:
        r = session.get(
            _YF_CHART_URL.format(ticker=ticker),
            headers=_COMMON_HEADERS,
            timeout=10,
        )
        r.raise_for_status()
        meta = r.json()["chart"]["result"][0]["meta"]
        return float(meta.get("regularMarketPrice") or meta.get("previousClose") or 0)
    except Exception as exc:
        logging.debug(f"[YF] {symbol}: {exc}")
        return 0.0


def fetch_via_yfinance(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: last_price} using Yahoo Finance chart API."""
    session = requests.Session()
    session.verify = _VERIFY

    # Prime the session with a cookie handshake
    try:
        session.get("https://fc.yahoo.com", timeout=5)
    except Exception:
        pass

    logging.info(f"[YF] Fetching {len(symbols)} symbols from Yahoo Finance …")
    prices: dict[str, float] = {}
    for sym in symbols:
        prices[sym] = _yf_price(session, sym)
        time.sleep(0.05)  # gentle rate-limiting

    fetched = sum(1 for v in prices.values() if v > 0)
    logging.info(f"[YF] Got prices for {fetched}/{len(symbols)} symbols.")
    return prices


# ---------------------------------------------------------------------------
# Source 2 – NSE India unofficial REST API
# ---------------------------------------------------------------------------

_NSE_QUOTE_URL = "https://www.nseindia.com/api/quote-equity?symbol={symbol}"


def fetch_via_nse(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: last_price} using NSE India equity quote API."""
    session = requests.Session()
    session.verify = _VERIFY
    session.headers.update(_COMMON_HEADERS)
    session.headers["Referer"] = "https://www.nseindia.com"

    # Prime cookies
    try:
        session.get("https://www.nseindia.com", timeout=10)
    except Exception as exc:
        logging.warning(f"[NSE] Cookie prime failed: {exc}")

    logging.info(f"[NSE] Fetching {len(symbols)} symbols from NSE India …")
    prices: dict[str, float] = {}
    for sym in symbols:
        try:
            r = session.get(
                _NSE_QUOTE_URL.format(symbol=sym),
                timeout=8,
            )
            r.raise_for_status()
            ltp = r.json().get("priceInfo", {}).get("lastPrice", 0.0)
            prices[sym] = float(ltp)
        except Exception as exc:
            logging.debug(f"[NSE] {sym}: {exc}")
            prices[sym] = 0.0
        time.sleep(0.15)  # avoid rate-limiting

    fetched = sum(1 for v in prices.values() if v > 0)
    logging.info(f"[NSE] Got prices for {fetched}/{len(symbols)} symbols.")
    return prices


# ---------------------------------------------------------------------------
# Core update logic
# ---------------------------------------------------------------------------

def detect_months(df: pd.DataFrame) -> list[str]:
    """Return futures month labels present in the CSV (e.g. ['JUN','JUL','AUG'])."""
    return [
        col.replace("LTP_", "")
        for col in df.columns
        if col.startswith("LTP_") and col != "LTP_nan"
    ]


def estimate_futures_price(spot: float, months_out: int) -> float:
    """Cost-of-carry estimate: F ≈ S * (1 + r * T)."""
    if spot <= 0:
        return 0.0
    rate = 0.10          # ~10 % p.a. risk-free rate (India)
    days = months_out * 30
    return round(spot * (1 + rate * days / 365), 2)


def update_csv(prices: dict[str, float]) -> None:
    """Write fetched prices into ALL_DATA.csv and ALL_DATA_original.csv."""
    try:
        df = pd.read_csv(ALL_DATA_CSV)
    except FileNotFoundError:
        logging.error(f"{ALL_DATA_CSV} not found – run initial setup first.")
        return

    months = detect_months(df)
    logging.info(f"Updating columns: LTP_nan + {['LTP_' + m for m in months]}")

    # Ensure all price columns are numeric before writing floats
    price_cols = (
        ["LTP_nan", "TOP BID_nan", "TOP ASK_nan"]
        + [f"LTP_{m}" for m in months]
        + [f"TOP BID_{m}" for m in months]
        + [f"TOP ASK_{m}" for m in months]
    )
    for col in price_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    for idx, row in df.iterrows():
        sym = str(row.get("tradingsymbol_nan", "")).strip()
        if not sym:
            continue
        spot = prices.get(sym, 0.0)
        if spot <= 0:
            continue

        # Spot columns
        df.at[idx, "LTP_nan"]       = spot
        df.at[idx, "TOP BID_nan"]   = round(spot * (1 - SPREAD_PCT), 2)
        df.at[idx, "TOP ASK_nan"]   = round(spot * (1 + SPREAD_PCT), 2)

        # Futures columns
        for i, month in enumerate(months, start=1):
            fut = estimate_futures_price(spot, i)
            df.at[idx, f"LTP_{month}"]       = fut
            df.at[idx, f"TOP BID_{month}"]   = round(fut * (1 - SPREAD_PCT), 2)
            df.at[idx, f"TOP ASK_{month}"]   = round(fut * (1 + SPREAD_PCT), 2)

    df.to_csv(ALL_DATA_CSV, index=False)
    df.to_csv(ORIGINAL_CSV, index=False)
    logging.info(f"Saved {ALL_DATA_CSV} and {ORIGINAL_CSV}.")


def run_once(source: str = "auto") -> None:
    try:
        df = pd.read_csv(ALL_DATA_CSV)
    except FileNotFoundError:
        logging.error(f"{ALL_DATA_CSV} not found.")
        return

    symbols = (
        df["tradingsymbol_nan"]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda s: s != ""]
        .tolist()
    )

    prices: dict[str, float] = {}

    if source in ("auto", "yfinance"):
        prices = fetch_via_yfinance(symbols)

    if source in ("auto", "nse") and sum(v > 0 for v in prices.values()) < len(symbols) // 2:
        logging.info("Falling back to NSE India API …")
        nse_prices = fetch_via_nse(symbols)
        for sym, price in nse_prices.items():
            if prices.get(sym, 0.0) == 0.0 and price > 0:
                prices[sym] = price

    fetched = sum(1 for v in prices.values() if v > 0)
    logging.info(f"Total: {fetched}/{len(symbols)} symbols with live prices. Updating CSV …")
    update_csv(prices)
    logging.info(f"Done at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch live NSE stock prices into ALL_DATA.csv"
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=0,
        metavar="SECONDS",
        help="If > 0, repeat every N seconds (e.g. --loop 30)",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "yfinance", "nse"],
        default="auto",
        help="Data source (default: auto = Yahoo Finance then NSE fallback)",
    )
    args = parser.parse_args()

    if args.loop > 0:
        logging.info(f"Loop mode: refreshing every {args.loop}s. Ctrl-C to stop.")
        while True:
            run_once(source=args.source)
            time.sleep(args.loop)
    else:
        run_once(source=args.source)


if __name__ == "__main__":
    main()
