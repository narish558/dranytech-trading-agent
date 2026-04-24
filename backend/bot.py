"""
Binance Claude AI Trading Agent — Backend
Render-ready: reads credentials from environment variables.
"""

import os
import time
import hmac
import hashlib
import requests
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from ai_agent import run_ai_cycle

app = Flask(__name__)
CORS(app, origins="*")  # Allow all origins (frontend can be hosted anywhere)

# ── State ──────────────────────────────────────────────────────────────────────
state = {
    # Credentials — loaded from env vars on startup, or set via /connect
    "api_key":        os.environ.get("BINANCE_API_KEY", ""),
    "api_secret":     os.environ.get("BINANCE_API_SECRET", ""),
    "anthropic_key":  os.environ.get("ANTHROPIC_API_KEY", ""),
    "testnet":        os.environ.get("TESTNET", "false").lower() == "true",
    "connected":      False,
    "agent_running":  False,
    "agent_mode":     "hybrid",
    "rules":          [],
    "log":            [],
    "trades":         [],
    "balances":       [],
    "ai_decisions":   [],
    "pnl_today":      0.0,
    "daily_loss":     0.0,
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

# ── Auto-connect on startup if env vars are set ────────────────────────────────
def try_auto_connect():
    if state["api_key"] and state["api_secret"]:
        try:
            r = signed_request("GET", "spot", "/api/v3/account")
            if r.status_code == 200:
                state["connected"] = True
                refresh_balances()
                log("Auto-connected via environment variables.", "ok")
                if state["anthropic_key"]:
                    log("Claude AI key loaded from environment.", "ok")
            else:
                log(f"Auto-connect failed: {r.json().get('msg','unknown')}", "warn")
        except Exception as e:
            log(f"Auto-connect error: {e}", "warn")
    else:
        log("No env vars set. Connect via dashboard.", "info")

# ── Helpers ────────────────────────────────────────────────────────────────────
def log(msg, level="info"):
    entry = {"time": datetime.now().strftime("%H:%M:%S"), "msg": msg, "level": level}
    state["log"].append(entry)
    if len(state["log"]) > 300:
        state["log"].pop(0)
    print(f"[{entry['time']}][{level.upper()}] {msg}")

def base_url(market="spot"):
    if market == "futures":
        return FUTURES_TEST if state["testnet"] else FUTURES_BASE
    return SPOT_TEST if state["testnet"] else SPOT_BASE

def signed_request(method, market, path, params=None):
    params = params or {}
    params["timestamp"] = int(time.time() * 1000)
    query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    sig = hmac.new(state["api_secret"].encode(), query.encode(), hashlib.sha256).hexdigest()
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

def place_order(rule, price):
    symbol = rule["pair"].replace("/", "")
    market = rule["market"].lower()
    side   = rule["side"]
    amount = float(rule["amount"])

    # Risk gate checks
    if amount > state["risk"]["max_trade_usdt"]:
        log(f"Blocked: ${amount} exceeds max ${state['risk']['max_trade_usdt']}", "warn")
        return None
    if state["daily_loss"] >= state["risk"]["daily_loss_limit"]:
        log("Blocked: daily loss limit reached. Agent paused.", "warn")
        return None
    open_count = len([t for t in state["trades"] if not t.get("closed")])
    if open_count >= state["risk"]["max_open_trades"]:
        log(f"Blocked: max open trades ({state['risk']['max_open_trades']}) reached.", "warn")
        return None

    qty  = round(amount / price, 6)
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
                "market":  rule["market"],
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
            sl_price = price * (1 - float(sl) / 100) if side == "BUY" else price * (1 + float(sl) / 100)
            log(f"FILLED: {side} {qty} {symbol} @ ${price:.4f} | SL=${sl_price:.4f} | ID={data['orderId']}", "ok")
            if tp:
                tp_price = price * (1 + float(tp) / 100) if side == "BUY" else price * (1 - float(tp) / 100)
                log(f"Take-profit target: ${tp_price:.4f} ({tp}%)", "info")
            refresh_balances()
            return trade
        else:
            log(f"Order rejected: {data.get('msg', data)}", "error")
            return None
    except Exception as e:
        log(f"Order exception: {e}", "error")
        return None

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
        log(f"RULE TRIGGERED: {rule['side']} {rule['pair']}", "ok")
        place_order(rule, price)
        rule["triggered"] = True

# ── Agent Loops ────────────────────────────────────────────────────────────────
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
        result = run_ai_cycle(
            pairs          = pairs,
            base_url       = base_url("spot"),
            balances       = state["balances"],
            trades         = state["trades"],
            risk           = state["risk"],
            api_key        = state["anthropic_key"],
            log_fn         = log,
            place_order_fn = place_order,
        )
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
    threads = []
    mode    = state["agent_mode"]
    if mode in ("rule", "hybrid"):
        t = threading.Thread(target=rule_loop, daemon=True)
        t.start()
        threads.append(t)
    if mode in ("ai", "hybrid"):
        if not state["anthropic_key"]:
            log("No Claude API key — AI mode skipped.", "warn")
        else:
            t = threading.Thread(target=ai_loop, daemon=True)
            t.start()
            threads.append(t)
    for t in threads:
        t.join()

# ── API Routes ─────────────────────────────────────────────────────────────────
@app.route("/connect", methods=["POST"])
def connect():
    d = request.json
    # Only override env vars if explicitly provided in request
    if d.get("api_key"):
        state["api_key"] = d["api_key"]
    if d.get("api_secret"):
        state["api_secret"] = d["api_secret"]
    if d.get("anthropic_key"):
        state["anthropic_key"] = d["anthropic_key"]
    state["testnet"] = d.get("testnet", state["testnet"])
    try:
        r = signed_request("GET", "spot", "/api/v3/account")
        if r.status_code == 200:
            state["connected"] = True
            refresh_balances()
            log("Connected to Binance API.", "ok")
            if state["anthropic_key"]:
                log("Claude AI key active.", "ok")
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
        if px:
            result[p] = px
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
        state["risk"]["ai_interval_sec"] = d["ai_interval_sec"]
    threading.Thread(target=agent_runner, daemon=True).start()
    log(f"Agent started in [{state['agent_mode'].upper()}] mode.", "ok")
    return jsonify({"ok": True, "mode": state["agent_mode"]})

@app.route("/agent/stop", methods=["POST"])
def stop_agent():
    state["agent_running"] = False
    log("Agent stopped by user.", "warn")
    return jsonify({"ok": True})

@app.route("/agent/analyze", methods=["POST"])
def manual_analyze():
    if not state["anthropic_key"]:
        return jsonify({"ok": False, "msg": "Claude API key not configured"}), 400
    pairs  = request.json.get("pairs", ["BTC/USDT", "ETH/USDT", "BNB/USDT"])
    result = run_ai_cycle(
        pairs          = pairs,
        base_url       = base_url("spot"),
        balances       = state["balances"],
        trades         = state["trades"],
        risk           = state["risk"],
        api_key        = state["anthropic_key"],
        log_fn         = log,
        place_order_fn = place_order,
    )
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

@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"ok": True, "log": state["log"][-150:]})

@app.route("/trades", methods=["GET"])
def get_trades():
    return jsonify({"ok": True, "trades": state["trades"]})

@app.route("/risk", methods=["POST"])
def set_risk():
    state["risk"].update(request.json)
    log("Risk settings updated.", "info")
    return jsonify({"ok": True})

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "Binance Claude AI Agent running", "connected": state["connected"]})

# ── Startup ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  Binance Claude AI Agent — Render-Ready Backend")
    print("=" * 55)
    threading.Thread(target=try_auto_connect, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
