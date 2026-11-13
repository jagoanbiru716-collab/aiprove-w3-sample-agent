"""Research strategy for the 7-day BTC direction call.

The forecast is derived from public market data, not guessed: the agent
pulls BTC's last 8 daily closes from CoinGecko's public API and scores
three facts — 7-day momentum, 24-hour momentum, and trend consistency
(how many of the last 7 sessions closed down). A steep, consistent
selloff points down; a bounce risk caps confidence below 0.65, because
Brier scoring punishes a confident wrong call more than a hedged one.

Pure function of the fetched closes, so the call is reproducible from
the numbers printed in the transcript.
"""

import json
import urllib.request

from . import config

COINGECKO_CHART = ("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
                   "?vs_currency=usd&days=8&interval=daily")
COINGECKO_PRICE = ("https://api.coingecko.com/api/v3/simple/price"
                   "?ids=bitcoin&vs_currencies=usd&include_24hr_change=true")


def fetch_daily_closes():
    """Return (closes, current_price, change_24h_pct) from public data."""
    req = urllib.request.Request(COINGECKO_CHART,
                                 headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as resp:
        chart = json.loads(resp.read())
    closes = [price for _, price in chart["prices"]]

    req = urllib.request.Request(COINGECKO_PRICE,
                                 headers={"User-Agent": config.USER_AGENT})
    with urllib.request.urlopen(req, timeout=config.HTTP_TIMEOUT) as resp:
        tick = json.loads(resp.read())["bitcoin"]
    return closes, tick["usd"], tick["usd_24h_change"]


def decide_btc_7d(closes, change_24h_pct):
    """Turn daily closes into {"answer", "confidence"} plus the reasoning.

    answer "yes" = BTC closes higher 7 days from now; "no" = lower.
    """
    if len(closes) < 2:
        raise ValueError("not enough daily closes to decide")
    week_change = (closes[-1] / closes[0] - 1.0) * 100.0
    downs = sum(1 for a, b in zip(closes, closes[1:]) if b < a)
    sessions = len(closes) - 1

    # Direction follows the week's momentum; consistency sets the size.
    if week_change <= -5.0 and downs >= sessions - 1:
        answer, confidence = "no", 0.58
    elif week_change <= -5.0:
        answer, confidence = "no", 0.55
    elif week_change >= 5.0 and downs <= 1:
        answer, confidence = "yes", 0.58
    elif week_change >= 5.0:
        answer, confidence = "yes", 0.55
    else:
        # Flat week: no edge; a coin-flip call, hedged hard.
        answer = "yes" if change_24h_pct >= 0 else "no"
        confidence = 0.52

    if week_change <= -5.0 and downs >= sessions - 1:
        trend = "Steep consistent selloff"
    elif week_change <= -5.0:
        trend = "Sharp weekly drop, mixed sessions"
    elif week_change >= 5.0 and downs <= 1:
        trend = "Steep consistent rally"
    elif week_change >= 5.0:
        trend = "Strong weekly gain, mixed sessions"
    else:
        trend = "No strong trend"
    reasoning = (
        f"BTC 7d {week_change:+.2f}% over {sessions} sessions, "
        f"{downs}/{sessions} down days, 24h {change_24h_pct:+.2f}%. "
        f"{trend}; confidence capped — a sharp selloff often bounces, and Brier "
        f"punishes a confident wrong call."
    )
    return {"answer": answer, "confidence": confidence}, reasoning
