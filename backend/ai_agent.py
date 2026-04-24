"""
Claude AI Trading Brain
Uses Anthropic Claude API to analyze markets and make real trade decisions.
"""

import json
import requests
from datetime import datetime

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """You are an expert cryptocurrency trading AI agent managing a real Binance account.

Your job is to analyze live market data and decide whether to BUY, SELL, or HOLD for each asset.

You will receive:
- Live prices and recent % changes for multiple pairs
- Current portfolio balances
- Active open positions
- Risk settings (max trade size, daily loss limit)
- Recent trade history
- Current market sentiment indicators

You must respond with ONLY valid JSON in this exact format:
{
  "analysis": "Brief market analysis in 2-3 sentences",
  "sentiment": "bullish | bearish | neutral",
  "decisions": [
    {
      "pair": "BTC/USDT",
      "market": "spot",
      "action": "BUY | SELL | HOLD",
      "amount_usdt": 100,
      "confidence": 0.75,
      "reason": "One sentence reason",
      "stop_loss_pct": 3.0,
      "take_profit_pct": 6.0
    }
  ],
  "risk_warning": "Any specific risk warning, or null"
}

STRICT RULES you must follow:
1. Never recommend an amount_usdt above the max_trade_usdt in risk settings
2. Always include stop_loss_pct (minimum 2%, maximum 10%)
3. Only output BUY/SELL when confidence >= 0.65
4. Output HOLD when uncertain — it is always better to do nothing than lose money
5. Never trade more than 3 pairs in a single cycle
6. If daily_loss_pct is above 50% of limit, be very conservative
7. Futures positions require higher confidence (>= 0.75)
8. Always explain your reasoning clearly

Remember: Capital preservation is the top priority. Consistent small gains beat large losses.
"""


def get_rsi_simple(prices: list) -> float:
    """Calculate a simple RSI from a list of closing prices."""
    if len(prices) < 14:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i-1]
        if diff > 0:
            gains.append(diff)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(diff))
    avg_gain = sum(gains[-14:]) / 14
    avg_loss = sum(losses[-14:]) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def fetch_klines(symbol: str, base_url: str, interval="1h", limit=24) -> list:
    """Fetch recent candlestick data for a symbol."""
    try:
        url = base_url + "/api/v3/klines"
        r = requests.get(url, params={"symbol": symbol, "interval": interval, "limit": limit}, timeout=8)
        data = r.json()
        if isinstance(data, list):
            return [float(c[4]) for c in data]  # closing prices
        return []
    except Exception:
        return []


def fetch_24h_ticker(symbol: str, base_url: str) -> dict:
    """Get 24h stats for a symbol."""
    try:
        r = requests.get(base_url + "/api/v3/ticker/24hr", params={"symbol": symbol}, timeout=5)
        d = r.json()
        return {
            "price": float(d.get("lastPrice", 0)),
            "change_pct": float(d.get("priceChangePercent", 0)),
            "high": float(d.get("highPrice", 0)),
            "low": float(d.get("lowPrice", 0)),
            "volume": float(d.get("volume", 0)),
            "quote_volume": float(d.get("quoteVolume", 0)),
        }
    except Exception:
        return {}


def build_market_context(pairs: list, base_url: str, balances: list, trades: list, risk: dict) -> dict:
    """Build the full market context to send to Claude."""
    market_data = {}
    for pair in pairs:
        symbol = pair.replace("/", "")
        ticker = fetch_24h_ticker(symbol, base_url)
        closes = fetch_klines(symbol, base_url)
        rsi = get_rsi_simple(closes) if closes else 50.0

        # Simple moving averages
        sma7  = round(sum(closes[-7:])  / min(7,  len(closes)), 4) if closes else None
        sma24 = round(sum(closes[-24:]) / min(24, len(closes)), 4) if closes else None

        market_data[pair] = {
            **ticker,
            "rsi_1h": rsi,
            "sma_7h": sma7,
            "sma_24h": sma24,
            "trend": "up" if (sma7 and sma24 and sma7 > sma24) else "down",
        }

    # Summarise portfolio
    portfolio = {b["asset"]: {"free": float(b["free"]), "locked": float(b["locked"])}
                 for b in balances if float(b["free"]) + float(b["locked"]) > 0}

    recent_trades = trades[-10:] if trades else []

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "market_data": market_data,
        "portfolio": portfolio,
        "recent_trades": recent_trades,
        "risk_settings": risk,
        "pairs_to_analyze": pairs,
    }


def ask_claude(context: dict, api_key: str) -> dict:
    """Send market context to Claude and get trading decisions."""
    user_message = f"""Analyze these live market conditions and give me your trading decisions:

{json.dumps(context, indent=2)}

Respond ONLY with the JSON format specified. No extra text."""

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "system": SYSTEM_PROMPT,
        "messages": [{"role": "user", "content": user_message}],
    }

    response = requests.post(ANTHROPIC_API, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()

    raw = data["content"][0]["text"].strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    return json.loads(raw)


def run_ai_cycle(pairs, base_url, balances, trades, risk, api_key, log_fn, place_order_fn):
    """
    Full AI agent cycle:
    1. Gather market data
    2. Ask Claude for decisions
    3. Execute approved trades
    Returns the Claude response dict.
    """
    log_fn("AI cycle: gathering market data for " + ", ".join(pairs), "info")

    try:
        context = build_market_context(pairs, base_url, balances, trades, risk)
    except Exception as e:
        log_fn(f"Market data error: {e}", "error")
        return None

    log_fn("Sending market data to Claude AI for analysis...", "info")

    try:
        response = ask_claude(context, api_key)
    except Exception as e:
        log_fn(f"Claude API error: {e}", "error")
        return None

    sentiment = response.get("sentiment", "neutral")
    analysis  = response.get("analysis", "")
    warning   = response.get("risk_warning")
    decisions = response.get("decisions", [])

    log_fn(f"Claude AI: [{sentiment.upper()}] {analysis}", "ok")
    if warning:
        log_fn(f"Claude risk warning: {warning}", "warn")

    for dec in decisions:
        pair       = dec.get("pair")
        action     = dec.get("action", "HOLD")
        amount     = dec.get("amount_usdt", 0)
        confidence = dec.get("confidence", 0)
        reason     = dec.get("reason", "")
        market     = dec.get("market", "spot")
        sl         = dec.get("stop_loss_pct", 3.0)
        tp         = dec.get("take_profit_pct", 6.0)

        log_fn(f"Decision: {action} {pair} ({market}) | confidence={confidence:.0%} | {reason}", "info")

        if action == "HOLD":
            log_fn(f"HOLD {pair} — no trade placed.", "info")
            continue

        if confidence < 0.65:
            log_fn(f"Skipping {pair}: confidence {confidence:.0%} below threshold.", "warn")
            continue

        # Build a synthetic rule for place_order
        rule = {
            "pair": pair,
            "market": market.capitalize(),
            "side": action,
            "amount": amount,
            "sl": sl,
            "tp": tp,
            "ai_decision": True,
        }

        # Fetch current price
        symbol = pair.replace("/", "")
        ticker = fetch_24h_ticker(symbol, base_url)
        price  = ticker.get("price")

        if not price:
            log_fn(f"Cannot get price for {pair}, skipping.", "error")
            continue

        log_fn(f"Executing AI trade: {action} ${amount} of {pair} @ ${price:.4f}", "ok")
        place_order_fn(rule, price)

    return response
