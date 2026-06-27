"""
Fetch live NSE stock data from the internet and update ALL_DATA.csv
so the Streamlit dashboard reflects current prices.

Data sources tried in order:
  1. Yahoo Finance via yfinance  (pip install yfinance)
  2. NSE India unofficial REST API  (no key needed, needs cookies)

Usage:
    python fetch_stock_data.py              # single fetch
    python fetch_stock_data.py --loop 30   # refresh every 30 seconds
    python fetch_stock_data.py --source nse  # force NSE source
"""

import argparse
import logging
import time
from datetime import datetime

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%H:%M:%S",
)

ALL_DATA_CSV = "ALL_DATA.csv"
ORIGINAL_CSV = "ALL_DATA_original.csv"
SPREAD_PCT = 0.001  # 0.1 % spread used to estimate bid/ask from LTP

# ---------------------------------------------------------------------------
# Source 1 – Yahoo Finance (yfinance)
# ---------------------------------------------------------------------------

def fetch_via_yfinance(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: last_price} using Yahoo Finance (.NS suffix for NSE)."""
    try:
        import yfinance as yf
    except ImportError:
        logging.warning("yfinance not installed. Run: pip install yfinance")
        return {}

    tickers = [s + ".NS" for s in symbols]
    logging.info(f"[yfinance] Fetching {len(tickers)} symbols …")

    try:
        raw = yf.download(
            tickers,
            period="1d",
            interval="1m",
            group_by="ticker",
            auto_adjust=True,
            progress=False,
            threads=True,
        )
    except Exception as exc:
        logging.warning(f"[yfinance] Download failed: {exc}")
        return {}

    prices: dict[str, float] = {}
    if len(tickers) == 1:
        sym = symbols[0]
        try:
            prices[sym] = float(raw["Close"].dropna().iloc[-1])
        except Exception:
            prices[sym] = 0.0
    else:
        for sym, ticker in zip(symbols, tickers):
            try:
                prices[sym] = float(raw[ticker]["Close"].dropna().iloc[-1])
            except Exception:
                prices[sym] = 0.0

    fetched = sum(1 for v in prices.values() if v > 0)
    logging.info(f"[yfinance] Got prices for {fetched}/{len(symbols)} symbols.")
    return prices


# ---------------------------------------------------------------------------
# Source 2 – NSE India unofficial REST API
# ---------------------------------------------------------------------------

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.nseindia.com",
}

def _nse_session():
    """Return a requests.Session pre-seeded with NSE cookies."""
    import requests
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    # Hit the homepage once to get session cookies
    session.get("https://www.nseindia.com", timeout=10)
    return session


def fetch_via_nse(symbols: list[str]) -> dict[str, float]:
    """Return {symbol: last_price} using NSE India's equity quote API."""
    try:
        import requests
    except ImportError:
        logging.warning("requests not installed. Run: pip install requests")
        return {}

    session = _nse_session()
    prices: dict[str, float] = {}
    for sym in symbols:
        try:
            url = f"https://www.nseindia.com/api/quote-equity?symbol={sym}"
            resp = session.get(url, timeout=8)
            resp.raise_for_status()
            data = resp.json()
            ltp = data.get("priceInfo", {}).get("lastPrice", 0.0)
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
    """Cost-of-carry estimate: F = S * e^(r*T) ≈ S * (1 + r*T)."""
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
        # Fill in only the zeros from yfinance
        for sym, price in nse_prices.items():
            if prices.get(sym, 0.0) == 0.0 and price > 0:
                prices[sym] = price

    fetched = sum(1 for v in prices.values() if v > 0)
    logging.info(
        f"Total: {fetched}/{len(symbols)} symbols with live prices. "
        f"Updating CSV …"
    )
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
        help="Data source to use (default: auto = yfinance then NSE fallback)",
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
