"""
DranyTech AI Trading Agent — Backend
Single-file, Render-ready. No external local imports.
"""

import os
import sys
import time
import json
import hmac
import hashlib
import requests
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins="*")

# ── State ──────────────────────────────────────────────────────────────────────
state = {
    "api_key":       os.environ.get("BINANCE_API_KEY", ""),
    "api_secret":    os.environ.get("BINANCE_API_SECRET", ""),
    "anthropic_key": os.environ.get("ANTHROPIC_API_KEY", ""),
    "testnet":       os.environ.get("TESTNET", "false").lower() == "true",
    "connected":     False,
    "agent_running": False,
    "agent_mode":    "hybrid",
    "rules":         [],
    "log":           [],
    "trades":        [],
    "balances":      [],
    "ai_decisions":  [],
    "pnl_today":     0.0,
    "daily_loss":    0.0,
    "risk": {
        "max_trade_usdt":   200,
        "daily_loss_limit": 100,
        "max_open_trades":  3,
        "default_sl_pct":   3.0,
        "futures_leverage": 3,
        "ai_interval_sec":  60,
        "ai_pairs":         ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT"],
    }
}

SPOT_BASE    = "https://api.binance.com"
FUTURES_BASE = "https://fapi.binance.com"
SPOT_TEST    = "https://testnet.binance.vision"
FUTURES_TEST = "https://testnet.binancefuture.com"

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL  = "claude-sonnet-4-6"

AI_SYSTEM = """You are an expert cryptocurrency trading AI agent managing a real Binance account.
Analyze live market data and decide BUY, SELL, or HOLD for each asset.

Respond ONLY with valid JSON in this exact format:
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

RULES:
1. Never recommend amount_usdt above max_trade_usdt in risk settings
2. Always include stop_loss_pct (min 2%, max 10%)
3. Only output BUY/SELL when confidence >= 0.65
4. Output HOLD when uncertain
5. Never trade more than 3 pairs per cycle
6. Capital preservation is the top priority
"""

# ── Logging ────────────────────────────────────────────────────────────────────
def log(msg, level="info"):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": str(msg), "level": level}
    state["log"].append(entry)
    if len(state["log"]) > 300:
        state["log"].pop(0)
    print(f"[{entry['time']}][{level.upper()}] {msg}", flush=True)

# ── Binance helpers ────────────────────────────────────────────────────────────
def base_url(market="spot"):
    if market == "futures":
        return FUTURES_TEST if state["testnet"] else FUTURES_BASE
    return SPOT_TEST if state["testnet"] else SPOT_BASE

def signed_request(method, market, path, params=None):
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(
        state["api_secret"].encode("utf-8"),
        query.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    query += f"&signature={sig}"
    url = base_url(market) + path + "?" + query
    headers = {"X-MBX-APIKEY": state["api_key"]}
    if method == "GET":
        return requests.get(url, headers=headers, timeout=10)
    return requests.post(url, headers=headers, timeout=10)

def get_price(symbol, market="spot"):
    try:
        path = "/api/v3/ticker/price" if market == "spot" else "/fapi/v1/ticker/price"
        r = requests.get(base_url(market) + path, params={"symbol": symbol}, timeout=5)
        return float(r.json()["price"])
    except Exception as e:
        log(f"Price error {symbol}: {e}", "error")
        return None

def get_ticker_24h(symbol, market="spot"):
    try:
        path = "/api/v3/ticker/24hr" if market == "spot" else "/fapi/v1/ticker/24hr"
        r = requests.get(base_url(market) + path, params={"symbol": symbol}, timeout=5)
        d = r.json()
        return {
            "price":      float(d.get("lastPrice", 0)),
            "change_pct": float(d.get("priceChangePercent", 0)),
            "high":       float(d.get("highPrice", 0)),
            "low":        float(d.get("lowPrice", 0)),
            "volume":     float(d.get("quoteVolume", 0)),
        }
    except Exception:
        return {}

def get_klines(symbol, market="spot", interval="1h", limit=24):
    try:
        path = "/api/v3/klines" if market == "spot" else "/fapi/v1/klines"
        r = requests.get(base_url(market) + path,
                         params={"symbol": symbol, "interval": interval, "limit": limit},
                         timeout=8)
        return [float(c[4]) for c in r.json()]
    except Exception:
        return []

def calc_rsi(closes):
    if len(closes) < 14:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-14:]) / 14
    al = sum(losses[-14:]) / 14
    if al == 0:
        return 100.0
    return round(100 - (100 / (1 + ag / al)), 2)

def refresh_balances():
    try:
        r = signed_request("GET", "spot", "/api/v3/account")
        if r.status_code == 200:
            state["balances"] = [
                b for b in r.json().get("balances", [])
                if float(b["free"]) + float(b["locked"]) > 0
            ]
    except Exception as e:
        log(f"Balance refresh error: {e}", "error")

def get_lot_size(symbol, market="spot"):
    """Fetch min qty and step size for a symbol from Binance exchange info."""
    try:
        path = "/api/v3/exchangeInfo" if market == "spot" else "/fapi/v1/exchangeInfo"
        r = requests.get(base_url(market) + path, params={"symbol": symbol}, timeout=8)
        data = r.json()
        for s in data.get("symbols", []):
            if s["symbol"] == symbol:
                for f in s.get("filters", []):
                    if f["filterType"] == "LOT_SIZE":
                        return float(f["minQty"]), float(f["stepSize"])
    except Exception as e:
        log(f"LOT_SIZE fetch error: {e}", "warn")
    return 0.001, 0.001  # safe fallback

def round_step(qty, step):
    """Round quantity down to nearest step size."""
    import math
    decimals = len(str(step).rstrip('0').split('.')[-1]) if '.' in str(step) else 0
    return round(math.floor(qty / step) * step, decimals)

def place_order(rule, price):
    symbol = rule["pair"].replace("/", "")
    market = rule["market"].lower()
    side   = rule["side"]
    amount = float(rule["amount"])

    if amount > state["risk"]["max_trade_usdt"]:
        log(f"Blocked: ${amount} > max ${state['risk']['max_trade_usdt']}", "warn")
        return None
    if state["daily_loss"] >= state["risk"]["daily_loss_limit"]:
        log("Blocked: daily loss limit reached.", "warn")
        return None
    open_count = len([t for t in state["trades"] if not t.get("closed")])
    if open_count >= state["risk"]["max_open_trades"]:
        log(f"Blocked: max open trades reached.", "warn")
        return None

    # Get correct lot size rules from Binance
    min_qty, step_size = get_lot_size(symbol, market)
    raw_qty = amount / price
    qty = round_step(raw_qty, step_size)

    # Check minimum quantity
    if qty < min_qty:
        log(f"Blocked: qty {qty} below Binance minimum {min_qty} for {symbol}. Increase trade amount.", "warn")
        return None

    log(f"Order: {side} {qty} {symbol} (min={min_qty}, step={step_size})", "info")
    params = {"symbol": symbol, "side": side, "type": "MARKET", "quantity": qty}
    if market == "futures":
        params["reduceOnly"] = "false"
    path = "/api/v3/order" if market == "spot" else "/fapi/v1/order"

    try:
        r    = signed_request("POST", market, path, params)
        data = r.json()
        if "orderId" in data:
            sl = rule.get("sl") or rule.get("stop_loss_pct") or state["risk"]["default_sl_pct"]
            tp = rule.get("tp") or rule.get("take_profit_pct")
            trade = {
                "time":    datetime.now().strftime("%H:%M:%S"),
                "pair":    rule["pair"],
                "market":  rule.get("market", "Spot"),
                "side":    side,
                "amount":  amount,
                "price":   price,
                "qty":     qty,
                "orderId": data["orderId"],
                "sl":      sl,
                "tp":      tp,
                "ai":      rule.get("ai_decision", False),
                "closed":  False,
            }
            state["trades"].append(trade)
            log(f"FILLED: {side} {qty} {symbol} @ ${price:.4f} | ID={data['orderId']}", "ok")
            refresh_balances()
            return trade
        else:
            log(f"Order rejected: {data.get('msg', data)}", "error")
            return None
    except Exception as e:
        log(f"Order exception: {e}", "error")
        return None

# ── Claude AI brain ────────────────────────────────────────────────────────────
def run_ai_cycle(pairs):
    if not state["anthropic_key"]:
        log("No Claude API key set.", "warn")
        return None

    log(f"AI cycle: gathering data for {', '.join(pairs)}", "info")
    market_data = {}
    for pair in pairs:
        symbol  = pair.replace("/", "")
        ticker  = get_ticker_24h(symbol)
        closes  = get_klines(symbol)
        rsi     = calc_rsi(closes)
        sma7    = round(sum(closes[-7:])  / min(7,  len(closes)), 4) if closes else None
        sma24   = round(sum(closes[-24:]) / min(24, len(closes)), 4) if closes else None
        market_data[pair] = {
            **ticker,
            "rsi_1h":  rsi,
            "sma_7h":  sma7,
            "sma_24h": sma24,
            "trend":   "up" if (sma7 and sma24 and sma7 > sma24) else "down",
        }

    portfolio = {
        b["asset"]: {"free": float(b["free"]), "locked": float(b["locked"])}
        for b in state["balances"]
    }

    context = {
        "timestamp":      datetime.utcnow().isoformat() + "Z",
        "market_data":    market_data,
        "portfolio":      portfolio,
        "recent_trades":  state["trades"][-10:],
        "risk_settings":  state["risk"],
        "pairs_to_analyze": pairs,
    }

    user_msg = f"Analyze these live market conditions and give trading decisions:\n\n{json.dumps(context, indent=2)}\n\nRespond ONLY with the JSON format specified."

    headers = {
        "x-api-key":         state["anthropic_key"],
        "anthropic-version": "2023-06-01",
        "content-type":      "application/json",
    }
    payload = {
        "model":      CLAUDE_MODEL,
        "max_tokens": 2048,
        "system":     AI_SYSTEM,
        "messages":   [{"role": "user", "content": user_msg}],
    }

    log("Sending market data to Claude AI...", "info")
    try:
        resp = requests.post(ANTHROPIC_API, headers=headers, json=payload, timeout=30)
        if resp.status_code != 200:
            log(f"Claude API error {resp.status_code}: {resp.text[:300]}", "error")
            return None
        raw = resp.json()["content"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())
    except Exception as e:
        log(f"Claude API error: {e}", "error")
        return None

    log(f"Claude [{result.get('sentiment','?').upper()}]: {result.get('analysis','')}", "ok")
    if result.get("risk_warning"):
        log(f"Claude warning: {result['risk_warning']}", "warn")

    for dec in result.get("decisions", []):
        action     = dec.get("action", "HOLD")
        pair       = dec.get("pair")
        confidence = dec.get("confidence", 0)
        reason     = dec.get("reason", "")
        amount     = dec.get("amount_usdt", 0)
        mkt        = dec.get("market", "spot")
        sl         = dec.get("stop_loss_pct", 3.0)
        tp         = dec.get("take_profit_pct", 6.0)

        log(f"Decision: {action} {pair} | conf={confidence:.0%} | {reason}", "info")

        if action == "HOLD" or confidence < 0.65:
            log(f"HOLD {pair} — skipping.", "info")
            continue

        symbol = pair.replace("/", "")
        ticker = get_ticker_24h(symbol)
        price  = ticker.get("price")
        if not price:
            log(f"Cannot get price for {pair}", "error")
            continue

        rule = {
            "pair": pair, "market": mkt.capitalize(),
            "side": action, "amount": amount,
            "sl": sl, "tp": tp, "ai_decision": True,
        }
        log(f"Executing AI trade: {action} ${amount} of {pair} @ ${price:.4f}", "ok")
        place_order(rule, price)

    return result

# ── Rule Engine ────────────────────────────────────────────────────────────────
def check_rule(rule):
    if rule.get("triggered"):
        return
    symbol  = rule["pair"].replace("/", "")
    market  = rule["market"].lower()
    price   = get_price(symbol, market)
    if not price:
        return
    trigger   = rule["trigger"]
    val       = float(rule["val"])
    triggered = False
    if trigger == "Price drops below" and price < val:
        triggered = True
    elif trigger == "Price rises above" and price > val:
        triggered = True
    elif trigger == "Price change % in 1h":
        baseline = rule.get("_baseline", price)
        rule["_baseline"] = baseline
        chg = (price - baseline) / baseline * 100
        if rule["side"] == "BUY" and chg <= -val:
            triggered = True
        elif rule["side"] == "SELL" and chg >= val:
            triggered = True
    log(f"Rule {rule['pair']}: ${price:.4f} | {trigger} {val} → {'HIT' if triggered else 'waiting'}")
    if triggered:
        log(f"TRIGGER: {rule['side']} {rule['pair']}", "ok")
        place_order(rule, price)
        rule["triggered"] = True

# ── Agent loops ────────────────────────────────────────────────────────────────
def rule_loop():
    log("Rule engine started — checking every 30s.", "ok")
    while state["agent_running"] and state["agent_mode"] in ("rule", "hybrid"):
        for rule in list(state["rules"]):
            check_rule(rule)
        time.sleep(30)

def ai_loop():
    interval = state["risk"].get("ai_interval_sec", 60)
    log(f"Claude AI agent started — analyzing every {interval}s.", "ok")
    while state["agent_running"] and state["agent_mode"] in ("ai", "hybrid"):
        pairs  = state["risk"].get("ai_pairs", ["BTC/USDT", "ETH/USDT"])
        result = run_ai_cycle(pairs)
        if result:
            state["ai_decisions"].append({
                "time":      datetime.now().strftime("%H:%M:%S"),
                "sentiment": result.get("sentiment"),
                "analysis":  result.get("analysis"),
                "decisions": result.get("decisions", []),
                "warning":   result.get("risk_warning"),
            })
            if len(state["ai_decisions"]) > 50:
                state["ai_decisions"].pop(0)
        time.sleep(interval)

def agent_runner():
    mode = state["agent_mode"]
    threads = []
    if mode in ("rule", "hybrid"):
        t = threading.Thread(target=rule_loop, daemon=True)
        t.start(); threads.append(t)
    if mode in ("ai", "hybrid"):
        if not state["anthropic_key"]:
            log("No Claude API key — AI mode skipped.", "warn")
        else:
            t = threading.Thread(target=ai_loop, daemon=True)
            t.start(); threads.append(t)
    for t in threads:
        t.join()

def get_my_ip():
    try:
        r = requests.get("https://api.ipify.org?format=json", timeout=5)
        ip = r.json().get("ip", "unknown")
        log(f">>> RENDER OUTBOUND IP: {ip} <<< (add this to Binance whitelist)", "ok")
        return ip
    except Exception:
        log("Could not detect outbound IP.", "warn")
        return None

def try_auto_connect():
    get_my_ip()
    if state["api_key"] and state["api_secret"]:
        try:
            r = signed_request("GET", "spot", "/api/v3/account")
            if r.status_code == 200:
                state["connected"] = True
                refresh_balances()
                log("Auto-connected via environment variables.", "ok")
                if state["anthropic_key"]:
                    log("Claude AI key loaded.", "ok")
            else:
                log(f"Auto-connect failed: {r.json().get('msg','unknown')}", "warn")
        except Exception as e:
            log(f"Auto-connect error: {e}", "warn")
    else:
        log("No API keys in environment. Connect via dashboard.", "info")

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "DranyTech AI Agent running", "connected": state["connected"]})

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "connected":     state["connected"],
        "testnet":       state["testnet"],
        "agent_running": state["agent_running"],
        "agent_mode":    state["agent_mode"],
        "has_ai":        bool(state["anthropic_key"]),
        "rule_count":    len(state["rules"]),
        "trade_count":   len(state["trades"]),
        "ai_decisions":  len(state["ai_decisions"]),
        "pnl_today":     state["pnl_today"],
        "daily_loss":    state["daily_loss"],
    })

@app.route("/connect", methods=["POST"])
def connect():
    d = request.json or {}
    if d.get("api_key"):       state["api_key"]       = d["api_key"]
    if d.get("api_secret"):    state["api_secret"]    = d["api_secret"]
    if d.get("anthropic_key"): state["anthropic_key"] = d["anthropic_key"]
    state["testnet"] = d.get("testnet", state["testnet"])
    try:
        r = signed_request("GET", "spot", "/api/v3/account")
        if r.status_code == 200:
            state["connected"] = True
            refresh_balances()
            log("Connected to Binance API.", "ok")
            return jsonify({"ok": True, "has_ai": bool(state["anthropic_key"])})
        return jsonify({"ok": False, "msg": r.json().get("msg", "Auth failed")}), 400
    except Exception as e:
        return jsonify({"ok": False, "msg": str(e)}), 500

@app.route("/balance", methods=["GET"])
def balance():
    if not state["connected"]:
        return jsonify({"ok": False, "msg": "Not connected"}), 401
    refresh_balances()
    return jsonify({"ok": True, "balances": state["balances"]})

@app.route("/prices", methods=["GET"])
def prices():
    result = {}
    for p in ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT"]:
        px = get_price(p)
        if px: result[p] = px
    return jsonify({"ok": True, "prices": result})

@app.route("/rules", methods=["GET"])
def get_rules():
    return jsonify({"ok": True, "rules": state["rules"]})

@app.route("/rules", methods=["POST"])
def add_rule():
    rule = request.json
    rule["id"]        = int(time.time() * 1000)
    rule["triggered"] = False
    state["rules"].append(rule)
    log(f"Rule added: {rule['side']} {rule['pair']} | {rule['trigger']} {rule['val']}", "ok")
    return jsonify({"ok": True, "rule": rule})

@app.route("/rules/<int:rule_id>", methods=["DELETE"])
def delete_rule(rule_id):
    state["rules"] = [r for r in state["rules"] if r["id"] != rule_id]
    return jsonify({"ok": True})

@app.route("/agent/start", methods=["POST"])
def start_agent():
    if not state["connected"]:
        return jsonify({"ok": False, "msg": "Not connected to Binance"}), 401
    if state["agent_running"]:
        return jsonify({"ok": False, "msg": "Agent already running"})
    d = request.json or {}
    state["agent_mode"]    = d.get("mode", "hybrid")
    state["agent_running"] = True
    if d.get("ai_interval_sec"):
        state["risk"]["ai_interval_sec"] = int(d["ai_interval_sec"])
    threading.Thread(target=agent_runner, daemon=True).start()
    log(f"Agent started in [{state['agent_mode'].upper()}] mode.", "ok")
    return jsonify({"ok": True, "mode": state["agent_mode"]})

@app.route("/agent/stop", methods=["POST"])
def stop_agent():
    state["agent_running"] = False
    log("Agent stopped.", "warn")
    return jsonify({"ok": True})

@app.route("/agent/analyze", methods=["POST"])
def manual_analyze():
    if not state["anthropic_key"]:
        return jsonify({"ok": False, "msg": "Claude API key not set"}), 400
    pairs  = (request.json or {}).get("pairs", ["BTC/USDT", "ETH/USDT", "BNB/USDT"])
    result = run_ai_cycle(pairs)
    if result:
        state["ai_decisions"].append({
            "time":      datetime.now().strftime("%H:%M:%S"),
            "sentiment": result.get("sentiment"),
            "analysis":  result.get("analysis"),
            "decisions": result.get("decisions", []),
            "warning":   result.get("risk_warning"),
        })
    return jsonify({"ok": bool(result), "result": result})

@app.route("/ai/decisions", methods=["GET"])
def ai_decisions():
    return jsonify({"ok": True, "decisions": state["ai_decisions"]})

@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"ok": True, "log": state["log"][-150:]})

@app.route("/trades", methods=["GET"])
def get_trades():
    return jsonify({"ok": True, "trades": state["trades"]})

@app.route("/risk", methods=["POST"])
def set_risk():
    state["risk"].update(request.json or {})
    log("Risk settings updated.", "info")
    return jsonify({"ok": True})

# ── Start ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  DranyTech Claude AI Trading Agent")
    print("=" * 55)
    sys.stdout.flush()
    threading.Thread(target=try_auto_connect, daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False)
