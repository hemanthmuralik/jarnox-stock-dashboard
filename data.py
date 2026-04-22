"""
data.py — Stock data fetching, cleaning, and metric computation.

Uses yfinance to pull real NSE/BSE data. Falls back to mock data
if the network is unavailable so the API stays functional offline.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional

# ── Tracked companies ─────────────────────────────────────────────────────────
# NSE symbols need ".NS" suffix for yfinance; BSE need ".BO"
COMPANIES = {
    "RELIANCE": {"name": "Reliance Industries", "exchange": "NSE", "sector": "Energy"},
    "TCS":      {"name": "Tata Consultancy Services", "exchange": "NSE", "sector": "IT"},
    "INFY":     {"name": "Infosys", "exchange": "NSE", "sector": "IT"},
    "HDFCBANK": {"name": "HDFC Bank", "exchange": "NSE", "sector": "Banking"},
    "ICICIBANK":{"name": "ICICI Bank", "exchange": "NSE", "sector": "Banking"},
    "WIPRO":    {"name": "Wipro", "exchange": "NSE", "sector": "IT"},
    "TATAMOTORS":{"name": "Tata Motors", "exchange": "NSE", "sector": "Auto"},
    "BAJFINANCE":{"name": "Bajaj Finance", "exchange": "NSE", "sector": "Finance"},
    "SUNPHARMA": {"name": "Sun Pharma", "exchange": "NSE", "sector": "Pharma"},
    "MARUTI":   {"name": "Maruti Suzuki", "exchange": "NSE", "sector": "Auto"},
}

# In-memory cache: symbol → (fetched_at, DataFrame)
_cache: dict = {}
CACHE_TTL_SECONDS = 300  # 5 minutes


def _yf_symbol(symbol: str) -> str:
    return f"{symbol}.NS"


def _is_cache_fresh(symbol: str) -> bool:
    if symbol not in _cache:
        return False
    fetched_at, _ = _cache[symbol]
    return (datetime.utcnow() - fetched_at).seconds < CACHE_TTL_SECONDS


def fetch_stock_data(symbol: str, period_days: int = 400) -> pd.DataFrame:
    """
    Fetch OHLCV data for `symbol`. Returns a cleaned DataFrame with
    computed metrics. Results are cached for CACHE_TTL_SECONDS.
    """
    if _is_cache_fresh(symbol):
        _, df = _cache[symbol]
        return df

    try:
        ticker = yf.Ticker(_yf_symbol(symbol))
        end = datetime.today()
        start = end - timedelta(days=period_days)
        raw = ticker.history(start=start, end=end)

        if raw.empty:
            raise ValueError(f"No data returned for {symbol}")

        df = _clean_and_enrich(raw, symbol)
        _cache[symbol] = (datetime.utcnow(), df)
        return df

    except Exception as e:
        # Graceful fallback to mock data so the API stays functional
        print(f"[WARN] yfinance failed for {symbol}: {e} — using mock data")
        df = _generate_mock_data(symbol, period_days)
        _cache[symbol] = (datetime.utcnow(), df)
        return df


def _clean_and_enrich(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Clean raw yfinance data and add all required + custom metrics."""
    df = raw[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index = pd.to_datetime(df.index)
    df.index.name = "Date"

    # ── Data cleaning ─────────────────────────────────────────────────────────
    # Drop rows where Close is 0 or NaN (data errors)
    df = df[df["Close"] > 0].dropna(subset=["Close"])

    # Forward-fill then back-fill remaining NaNs (handles single missing days)
    df = df.ffill().bfill()

    # ── Required metrics ──────────────────────────────────────────────────────
    # Daily Return = (Close - Open) / Open
    df["Daily_Return"] = (df["Close"] - df["Open"]) / df["Open"].replace(0, np.nan)

    # 7-day Moving Average of Close
    df["MA7"] = df["Close"].rolling(window=7, min_periods=1).mean()

    # 20-day Moving Average (bonus — useful for trend signals)
    df["MA20"] = df["Close"].rolling(window=20, min_periods=1).mean()

    # ── Custom metric: Volatility Score ───────────────────────────────────────
    # Rolling 14-day standard deviation of daily returns, normalised to 0–100.
    # High score = high price swings = higher risk.
    rolling_std = df["Daily_Return"].rolling(window=14, min_periods=1).std()
    max_std = rolling_std.max()
    df["Volatility_Score"] = (
        (rolling_std / max_std * 100).fillna(0).round(2)
        if max_std > 0 else 0.0
    )

    # ── Custom metric: Momentum Signal ───────────────────────────────────────
    # MA7 > MA20 → bullish momentum (1), else bearish (-1), neutral (0)
    df["Momentum"] = np.where(
        df["MA7"] > df["MA20"] * 1.005, 1,
        np.where(df["MA7"] < df["MA20"] * 0.995, -1, 0)
    )

    df = df.round(4)
    return df


def _generate_mock_data(symbol: str, days: int = 400) -> pd.DataFrame:
    """Deterministic mock OHLCV data for offline/testing use."""
    np.random.seed(abs(hash(symbol)) % (2**31))
    dates = pd.date_range(end=datetime.today(), periods=days, freq="B")
    base = 1000 + abs(hash(symbol)) % 3000
    returns = np.random.normal(0.0003, 0.015, days)
    closes = base * np.exp(np.cumsum(returns))
    opens  = closes * (1 + np.random.normal(0, 0.005, days))
    highs  = np.maximum(opens, closes) * (1 + abs(np.random.normal(0, 0.008, days)))
    lows   = np.minimum(opens, closes) * (1 - abs(np.random.normal(0, 0.008, days)))
    volumes = np.random.randint(500_000, 5_000_000, days).astype(float)

    raw = pd.DataFrame({
        "Open": opens, "High": highs, "Low": lows,
        "Close": closes, "Volume": volumes,
    }, index=dates)
    raw.index.name = "Date"
    return _clean_and_enrich(raw, symbol)


# ── Derived computations ──────────────────────────────────────────────────────

def get_52_week_stats(df: pd.DataFrame) -> dict:
    """52-week high, low, and average close from the last 252 trading days."""
    year_df = df.tail(252)
    return {
        "high_52w":  round(float(year_df["Close"].max()), 2),
        "low_52w":   round(float(year_df["Close"].min()), 2),
        "avg_close": round(float(year_df["Close"].mean()), 2),
        "current":   round(float(df["Close"].iloc[-1]), 2),
        "ytd_return": round(
            float((df["Close"].iloc[-1] - year_df["Close"].iloc[0])
                  / year_df["Close"].iloc[0] * 100), 2
        ),
    }


def compute_correlation(df1: pd.DataFrame, df2: pd.DataFrame) -> float:
    """Pearson correlation between the daily returns of two stocks."""
    merged = pd.merge(
        df1[["Daily_Return"]].rename(columns={"Daily_Return": "r1"}),
        df2[["Daily_Return"]].rename(columns={"Daily_Return": "r2"}),
        left_index=True, right_index=True,
        how="inner",
    )
    if len(merged) < 5:
        return 0.0
    return round(float(merged["r1"].corr(merged["r2"])), 4)
