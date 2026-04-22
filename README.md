# Stock Data Intelligence Dashboard

A mini financial data platform built for the JarNox internship assignment.
Fetches real NSE stock data, computes key metrics, and serves a live dashboard.

---

## Live Demo

> ## Live Demo

> **https://jarnox-stock-dashboard-0uhq.onrender.com**

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11 |
| Backend | FastAPI |
| Data | yfinance (real NSE data), Pandas, NumPy |
| Frontend | HTML + Chart.js (no build step) |
| Deployment | Render (free tier) |

---

## Local Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/hemanthmuralik/stock-dashboard.git
cd stock-dashboard

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the server
uvicorn main:app --reload

# 5. Open the dashboard
# http://127.0.0.1:8000
# Swagger UI: http://127.0.0.1:8000/docs
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/companies` | All tracked stocks with latest price and daily change |
| GET | `/data/{symbol}?days=30` | OHLCV + metrics for last N days (default 30) |
| GET | `/summary/{symbol}` | 52-week high/low, YTD return, volatility, momentum |
| GET | `/compare?symbol1=INFY&symbol2=TCS&days=90` | Normalised performance + correlation |
| GET | `/gainers-losers` | Today's top 3 gainers and losers |
| GET | `/docs` | Swagger interactive API docs |

### Sample curl commands

```bash
# List all companies
curl http://localhost:8000/companies

# Last 30 days of TCS data
curl http://localhost:8000/data/TCS

# 90-day data
curl "http://localhost:8000/data/INFY?days=90"

# Full summary for RELIANCE
curl http://localhost:8000/summary/RELIANCE

# Compare INFY vs TCS over 90 days
curl "http://localhost:8000/compare?symbol1=INFY&symbol2=TCS&days=90"

# Top gainers / losers
curl http://localhost:8000/gainers-losers
```

---

## Tracked Stocks (10 NSE-listed companies)

| Symbol | Company | Sector |
|---|---|---|
| RELIANCE | Reliance Industries | Energy |
| TCS | Tata Consultancy Services | IT |
| INFY | Infosys | IT |
| HDFCBANK | HDFC Bank | Banking |
| ICICIBANK | ICICI Bank | Banking |
| WIPRO | Wipro | IT |
| TATAMOTORS | Tata Motors | Auto |
| BAJFINANCE | Bajaj Finance | Finance |
| SUNPHARMA | Sun Pharma | Pharma |
| MARUTI | Maruti Suzuki | Auto |

---

## Metrics Computed

**Required:**
- **Daily Return** = (Close − Open) / Open
- **7-day Moving Average** (MA7) of Close
- **52-week High / Low** (last 252 trading days)

**Custom additions:**
- **20-day Moving Average** (MA20) — standard trend signal alongside MA7
- **Volatility Score** (0–100) — rolling 14-day std dev of daily returns, normalised. High = high price swings = higher risk.
- **Momentum Signal** — Bullish / Bearish / Neutral based on MA7 vs MA20 crossover (+/− 0.5% band)
- **Correlation** (in `/compare`) — Pearson correlation of daily returns between two stocks

---

## Data Handling

- Data is fetched via **yfinance** from Yahoo Finance (real NSE prices with `.NS` suffix)
- **Cleaning steps:**
  - Rows with zero or null Close price are dropped
  - Remaining NaNs forward-filled then back-filled (handles single missing trading days)
  - Date index normalised to `YYYY-MM-DD`
- **Caching:** Results cached in-memory for 5 minutes to avoid rate-limiting yfinance
- **Offline fallback:** If yfinance is unavailable, deterministic mock data is generated so the API stays functional

---

## Project Structure

```
stock-dashboard/
├── main.py          # FastAPI app, all endpoints
├── data.py          # Data fetching, cleaning, metric computation
├── requirements.txt
├── README.md
└── static/
    └── index.html   # Dashboard UI (Chart.js, no build step)
```

---

## Dashboard Features

- Sidebar with all 10 stocks, live price change %
- Metric cards: current price, 52W high/low, YTD return, momentum signal
- Price chart with MA7 and MA20 overlays, 30D / 90D / 180D / 1Y filters
- Stock comparison with normalised performance chart + correlation score
- Top gainers/losers table
- Volatility score bars for all stocks

---

## One Thing I'd Add With More Time

A simple **linear regression price projection** using the last 30 days of closing prices — shown as a dashed continuation line on the chart. It's not a reliable prediction, but it communicates trend direction clearly and is a natural extension of the MA indicators already computed.
