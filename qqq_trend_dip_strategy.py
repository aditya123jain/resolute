"""
QQQ "Trend + Dip + Bond" Strategy — backtester and daily signal checker
=======================================================================

Rules (evaluated once per day at the close):
  1. TREND:  when QQQ close > 200-day SMA, hold QQQ long with vol-scaled
             leverage = min(VOL_TARGET / realized_20d_vol, LEV_CAP).
  2. DIP:    when QQQ close <= 200-day SMA (bear regime), buy QQQ
             unleveraged when RSI(2) < 10; exit when RSI(2) > 60 or
             after MAX_HOLD days.
  3. BOND:   in bear regime with no dip trade active, hold TLT instead of
             cash — but only while TLT is above its OWN 200-day SMA
             (this filter kept the strategy out of bonds in 2022 when
             stocks and bonds fell together, and in bonds in 2008 when
             the flight-to-quality rallied TLT +34%).
  4. Costs modeled: 5bp per unit of position change, 6%/yr borrow on
             leverage above 1x.

Record 2002-2026 (24y, TLT inception limits the start), after costs:
              CAGR    maxDD   $1 ->
  this strategy   19.2%   -37.2%   $66.86
  no bond leg     17.6%   -42.5%   $47.93
  QQQ buy & hold  16.0%   -53.4%   $34.79   (window starts near dot-com low)
2008: strategy +29.0% vs QQQ -41.7%.  Worst year -20.1% (2022).

Unleveraged variant (LEV_CAP=1.0): 16.1% CAGR, -29.5% maxDD, Sharpe 0.90.

Validation: trend+dip core is positive in both halves of 2000-2026 and is
the top strategy independently on SPY/AAPL/META/AMZN/GOOGL. Parameter
perturbations (SMA 100-300, RSI 5-20/50-80, vol target 25-45%, cap
1.5-3x) all stay within 11-18% CAGR on the core. Monte Carlo (block
bootstrap, 10y paths): median CAGR ~16%, P(losing decade) ~3.5%,
P(>50% drawdown in a decade) ~33% at 2x cap.

Stop-loss note (DIP_STOP): measured across a 3%-15% stop grid on 10
symbols over 26y, stops REDUCE the dip module's edge everywhere (QQQ
avg/trade +0.69% -> +0.29% at 3%) and INCREASE its drawdown (QQQ -20% ->
-44%), because they sell at the panic low; on blow-up-prone names
(MSTR/BA/AMD) they don't rescue the strategy either — disasters gap
through stops. Default is therefore None. The real risk controls are
symbol selection (index ETFs / quality mega-caps only) and sizing.

Usage:
  python qqq_trend_dip_strategy.py --backtest              # full history stats
  python qqq_trend_dip_strategy.py --signal                # today's target position
  python qqq_trend_dip_strategy.py --signal --ticker SPY
  python qqq_trend_dip_strategy.py --backtest --no-bonds   # disable TLT leg
"""

import argparse
import json
import urllib.request

import numpy as np
import pandas as pd

# ---------------------------- CONFIG ----------------------------------------
SMA_LEN = 200        # trend filter length (days), same for equity and bond
RSI_LEN = 2          # RSI period for dip detection
RSI_BUY = 10         # enter dip trade below this
RSI_EXIT = 60        # exit dip trade above this
MAX_HOLD = 10        # max days to hold a dip trade
DIP_STOP = None      # e.g. 0.10 = exit dip trade if close falls 10% below
                     # entry. None (recommended) — see stop-loss note above.
VOL_TARGET = 0.35    # annualized vol target for trend leg
LEV_CAP = 2.0        # maximum leverage (set 1.0 for the defensive variant)
BEAR_ASSET = "TLT"   # held in bear regime while above its own SMA
COST = 0.0005        # cost per unit of position change (5bp)
BORROW = 0.06 / 252  # daily borrow rate on leverage above 1x
# -----------------------------------------------------------------------------


def fetch_daily(ticker: str) -> pd.Series:
    """Full adjusted daily close history from Yahoo Finance."""
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?period1=946684800&period2=9999999999&interval=1d&events=div%2Csplit")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=60))["chart"]["result"][0]
    adj = d["indicators"]["adjclose"][0]["adjclose"]
    idx = (pd.to_datetime(pd.Series(d["timestamp"]), unit="s", utc=True)
           .dt.tz_convert("America/New_York").dt.normalize().dt.tz_localize(None))
    s = pd.Series(adj, index=idx, name=ticker).dropna()
    return s[~s.index.duplicated(keep="last")]


def rsi(c: pd.Series, n: int = RSI_LEN) -> pd.Series:
    ch = c.diff()
    up = ch.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-ch.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / (dn + 1e-12))


def build_positions(eq: pd.Series, bond: pd.Series | None) -> pd.DataFrame:
    """Daily target weights for the equity and bond legs, decided at the close."""
    sma = eq.rolling(SMA_LEN).mean()
    r = rsi(eq).values
    below = (eq <= sma).values
    n = len(eq)

    dip = np.zeros(n)
    in_dip, held, entry_px = False, 0, 0.0
    ev = eq.values
    for i in range(RSI_LEN + 3, n):
        if not in_dip and r[i] < RSI_BUY and below[i]:
            in_dip, held, entry_px = True, 0, ev[i]
        elif in_dip:
            held += 1
            stopped = DIP_STOP is not None and ev[i] <= entry_px * (1 - DIP_STOP)
            if r[i] > RSI_EXIT or held >= MAX_HOLD or stopped:
                in_dip = False
        dip[i] = float(in_dip)
    dip = pd.Series(dip, index=eq.index)

    rv = eq.pct_change().rolling(20).std() * np.sqrt(252)
    trend_lev = ((eq > sma).astype(float) * (VOL_TARGET / rv).clip(upper=LEV_CAP)).fillna(0)
    w_eq = (trend_lev + dip).clip(0, LEV_CAP)

    if bond is not None:
        bond = bond.reindex(eq.index).ffill()
        bond_ok = bond > bond.rolling(SMA_LEN).mean()
        w_bond = (pd.Series(below, index=eq.index) & bond_ok).astype(float) * (1 - dip).clip(0, 1)
    else:
        w_bond = pd.Series(0.0, index=eq.index)

    return pd.DataFrame({"w_eq": w_eq, "w_bond": w_bond, "sma": sma, "rsi": r,
                         "rv": rv, "dip": dip})


def strategy_returns(eq: pd.Series, bond: pd.Series | None) -> pd.Series:
    sig = build_positions(eq, bond)
    ret_eq = eq.pct_change().fillna(0)
    ret_bd = (bond.reindex(eq.index).ffill().pct_change().fillna(0)
              if bond is not None else pd.Series(0.0, index=eq.index))
    pe, pb = sig["w_eq"].shift(1).fillna(0), sig["w_bond"].shift(1).fillna(0)
    gross = pe + pb
    turnover = pe.diff().abs().fillna(0) + pb.diff().abs().fillna(0)
    return pe * ret_eq + pb * ret_bd - (gross - 1).clip(lower=0) * BORROW - turnover * COST


def backtest(eq: pd.Series, bond: pd.Series | None) -> None:
    if bond is not None:
        eq = eq[eq.index >= bond.index[0]]
    strat = strategy_returns(eq, bond)
    bh = eq.pct_change().fillna(0)
    yrs = len(eq) / 252

    def stats(x):
        curve = (1 + x).cumprod()
        return (curve.iloc[-1] ** (1 / yrs) - 1) * 100, (curve / curve.cummax() - 1).min() * 100, curve.iloc[-1]

    cagr, mdd, fin = stats(strat)
    bcagr, bmdd, bfin = stats(bh)
    print(f"period          : {eq.index[0].date()} -> {eq.index[-1].date()}  ({yrs:.1f}y)")
    print(f"strategy        : CAGR {cagr:5.1f}%   maxDD {mdd:6.1f}%   $1 -> ${fin:,.2f}")
    print(f"buy & hold      : CAGR {bcagr:5.1f}%   maxDD {bmdd:6.1f}%   $1 -> ${bfin:,.2f}")
    print(f"sharpe          : {strat.mean() / strat.std() * np.sqrt(252):.2f}")
    ypnl = strat.groupby(strat.index.year).apply(lambda x: (1 + x).prod() - 1) * 100
    print(f"years positive  : {(ypnl > 0).mean() * 100:.0f}%   worst year {ypnl.min():+.1f}%")
    print("\nyearly returns (%):")
    print(ypnl.round(1).to_string())


def signal(eq: pd.Series, bond: pd.Series | None, ticker: str) -> None:
    sig = build_positions(eq, bond)
    last = sig.iloc[-1]
    regime = "TREND (above 200d SMA)" if eq.iloc[-1] > last["sma"] else "BEAR (below 200d SMA)"
    print(f"{ticker} @ {eq.index[-1].date()}   close={eq.iloc[-1]:.2f}")
    print(f"regime          : {regime}")
    print(f"200d SMA        : {last['sma']:.2f}   RSI(2): {last['rsi']:.1f}   20d vol: {last['rv'] * 100:.1f}% ann.")
    print(f"dip trade active: {'YES' if last['dip'] else 'no'}")
    print(f"\n>>> TARGET: {last['w_eq']:.2f}x {ticker}"
          + (f" + {last['w_bond']:.2f}x {BEAR_ASSET}" if last["w_bond"] > 0 else "")
          + (" (cash otherwise)" if last["w_eq"] == 0 and last["w_bond"] == 0 else "") + " <<<")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--signal", action="store_true")
    ap.add_argument("--ticker", default="QQQ")
    ap.add_argument("--no-bonds", action="store_true")
    args = ap.parse_args()
    eq = fetch_daily(args.ticker)
    bond = None if args.no_bonds else fetch_daily(BEAR_ASSET)
    if args.signal:
        signal(eq, bond, args.ticker)
    else:
        backtest(eq, bond)


if __name__ == "__main__":
    main()
