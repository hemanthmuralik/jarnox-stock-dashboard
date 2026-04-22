"""
main.py — SkillBridge Stock Intelligence API
FastAPI backend for the JarNox internship assignment.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Optional
import pandas as pd
import os

from data import (
    COMPANIES,
    compute_correlation,
    fetch_stock_data,
    get_52_week_stats,
)

app = FastAPI(
    title="Stock Data Intelligence API",
    description=(
        "Mini financial data platform. Fetches real NSE stock data via yfinance, "
        "computes key metrics, and serves insights through clean REST endpoints."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the dashboard at /
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
def serve_dashboard():
    return FileResponse("static/index.html")


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok", "version": "1.0.0"}


# ── Endpoint 1: /companies ────────────────────────────────────────────────────

@app.get("/companies", tags=["stocks"])
def list_companies():
    """
    Returns all tracked companies with their latest price and daily return.
    """
    result = []
    for symbol, meta in COMPANIES.items():
        try:
            df = fetch_stock_data(symbol, period_days=10)
            latest = df.iloc[-1]
            prev    = df.iloc[-2] if len(df) > 1 else df.iloc[-1]
            change_pct = round(
                (float(latest["Close"]) - float(prev["Close"]))
                / float(prev["Close"]) * 100, 2
            )
            result.append({
                "symbol":       symbol,
                "name":         meta["name"],
                "sector":       meta["sector"],
                "exchange":     meta["exchange"],
                "current_price": round(float(latest["Close"]), 2),
                "change_pct":   change_pct,
                "volume":       int(latest["Volume"]),
            })
        except Exception as e:
            result.append({
                "symbol":   symbol,
                "name":     meta["name"],
                "sector":   meta["sector"],
                "exchange": meta["exchange"],
                "error":    str(e),
            })
    return {"companies": result, "total": len(result)}


# ── Endpoint 2: /data/{symbol} ────────────────────────────────────────────────

@app.get("/data/{symbol}", tags=["stocks"])
def get_stock_data(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365, description="Number of trading days to return"),
):
    """
    Returns OHLCV + computed metrics for the last `days` trading days.
    Includes: Close, Open, High, Low, Volume, Daily_Return, MA7, MA20,
    Volatility_Score, Momentum.
    """
    symbol = symbol.upper()
    if symbol not in COMPANIES:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found. Call /companies for the full list.",
        )

    df = fetch_stock_data(symbol, period_days=max(days + 30, 60))
    df = df.tail(days)

    records = []
    for date, row in df.iterrows():
        records.append({
            "date":             date.strftime("%Y-%m-%d"),
            "open":             round(float(row["Open"]), 2),
            "high":             round(float(row["High"]), 2),
            "low":              round(float(row["Low"]), 2),
            "close":            round(float(row["Close"]), 2),
            "volume":           int(row["Volume"]),
            "daily_return":     round(float(row["Daily_Return"]) * 100, 4),  # as %
            "ma7":              round(float(row["MA7"]), 2),
            "ma20":             round(float(row["MA20"]), 2),
            "volatility_score": float(row["Volatility_Score"]),
            "momentum":         int(row["Momentum"]),
        })

    return {
        "symbol":  symbol,
        "name":    COMPANIES[symbol]["name"],
        "days":    days,
        "records": records,
    }


# ── Endpoint 3: /summary/{symbol} ────────────────────────────────────────────

@app.get("/summary/{symbol}", tags=["stocks"])
def get_summary(symbol: str):
    """
    Returns a full summary: 52-week high/low, average close, YTD return,
    latest metrics, and a volatility assessment.
    """
    symbol = symbol.upper()
    if symbol not in COMPANIES:
        raise HTTPException(
            status_code=404,
            detail=f"Symbol '{symbol}' not found. Call /companies for the full list.",
        )

    df = fetch_stock_data(symbol, period_days=400)
    stats = get_52_week_stats(df)
    latest = df.iloc[-1]
    last_30 = df.tail(30)

    # Average volatility over last 30 days
    avg_volatility = round(float(last_30["Volatility_Score"].mean()), 2)
    momentum_label = {1: "Bullish", -1: "Bearish", 0: "Neutral"}.get(
        int(latest["Momentum"]), "Neutral"
    )

    return {
        "symbol":          symbol,
        "name":            COMPANIES[symbol]["name"],
        "sector":          COMPANIES[symbol]["sector"],
        **stats,
        "avg_daily_return_pct": round(
            float(df.tail(30)["Daily_Return"].mean()) * 100, 4
        ),
        "avg_volatility_30d":   avg_volatility,
        "volatility_level":     (
            "High" if avg_volatility > 60
            else "Medium" if avg_volatility > 30
            else "Low"
        ),
        "momentum_signal":      momentum_label,
        "latest_close":         round(float(latest["Close"]), 2),
        "latest_volume":        int(latest["Volume"]),
    }


# ── Endpoint 4: /compare (Bonus) ─────────────────────────────────────────────

@app.get("/compare", tags=["stocks"])
def compare_stocks(
    symbol1: str = Query(..., description="First stock symbol, e.g. INFY"),
    symbol2: str = Query(..., description="Second stock symbol, e.g. TCS"),
    days: int = Query(default=90, ge=7, le=365),
):
    """
    Side-by-side comparison of two stocks: normalised price performance,
    correlation of daily returns, and key metric differences.
    """
    s1, s2 = symbol1.upper(), symbol2.upper()
    for s in [s1, s2]:
        if s not in COMPANIES:
            raise HTTPException(
                status_code=404,
                detail=f"Symbol '{s}' not found. Call /companies for the full list.",
            )

    df1 = fetch_stock_data(s1, period_days=days + 30).tail(days)
    df2 = fetch_stock_data(s2, period_days=days + 30).tail(days)

    correlation = compute_correlation(df1, df2)

    def _series(df: pd.DataFrame):
        base = float(df["Close"].iloc[0])
        return [
            {
                "date":        d.strftime("%Y-%m-%d"),
                "close":       round(float(r["Close"]), 2),
                "normalised":  round(float(r["Close"]) / base * 100, 4),
                "daily_return": round(float(r["Daily_Return"]) * 100, 4),
            }
            for d, r in df.iterrows()
        ]

    def _stats(symbol: str, df: pd.DataFrame) -> dict:
        stats = get_52_week_stats(df)
        return {
            "symbol":      symbol,
            "name":        COMPANIES[symbol]["name"],
            "sector":      COMPANIES[symbol]["sector"],
            "total_return_pct": round(
                (float(df["Close"].iloc[-1]) - float(df["Close"].iloc[0]))
                / float(df["Close"].iloc[0]) * 100, 2
            ),
            "avg_daily_return_pct": round(
                float(df["Daily_Return"].mean()) * 100, 4
            ),
            "avg_volatility": round(float(df["Volatility_Score"].mean()), 2),
            **stats,
        }

    return {
        "days":        days,
        "correlation": correlation,
        "correlation_label": (
            "Strong positive" if correlation > 0.7
            else "Moderate positive" if correlation > 0.4
            else "Weak/no correlation" if correlation > -0.4
            else "Negative correlation"
        ),
        "stock1": {**_stats(s1, df1), "series": _series(df1)},
        "stock2": {**_stats(s2, df2), "series": _series(df2)},
    }


# ── Endpoint 5: /gainers-losers (Bonus) ──────────────────────────────────────

@app.get("/gainers-losers", tags=["stocks"])
def top_gainers_losers():
    """Returns today's top gainers and losers among tracked stocks."""
    data = []
    for symbol in COMPANIES:
        try:
            df = fetch_stock_data(symbol, period_days=5)
            if len(df) >= 2:
                latest = float(df["Close"].iloc[-1])
                prev   = float(df["Close"].iloc[-2])
                chg    = round((latest - prev) / prev * 100, 2)
                data.append({"symbol": symbol, "name": COMPANIES[symbol]["name"],
                              "close": round(latest, 2), "change_pct": chg})
        except Exception:
            pass

    data.sort(key=lambda x: x["change_pct"], reverse=True)
    return {
        "top_gainers": data[:3],
        "top_losers":  list(reversed(data[-3:])),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
