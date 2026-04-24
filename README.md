# Binance AI Trading Agent

A real automated trading system for Binance Spot & Futures markets.

---

## What's Included

```
binance-agent/
├── backend/
│   ├── bot.py              ← Python backend (connects to real Binance API)
│   └── requirements.txt    ← Python dependencies
├── frontend/
│   └── index.html          ← Web dashboard (open in browser)
└── README.md
```

---

## Setup Instructions

### Step 1 — Install Python
Make sure Python 3.8+ is installed:
```bash
python --version
```
Download from https://python.org if needed.

### Step 2 — Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 3 — Run the backend
```bash
python bot.py
```
You should see:
```
==================================================
  Binance AI Trading Agent — Backend
  Running at http://localhost:5000
==================================================
```

### Step 4 — Open the frontend
Open `frontend/index.html` in your browser (double-click it, or drag it into Chrome/Firefox).

### Step 5 — Get Binance API Keys
1. Go to https://www.binance.com → Profile → API Management
2. Click "Create API" → System Generated → name it
3. Enable: ✓ Read Info, ✓ Spot Trading, ✓ Futures Trading
4. Keep ✗ Withdrawals DISABLED
5. Whitelist your IP address for safety

### Step 6 — Connect & Trade
1. Paste your API Key and Secret in the SETUP tab
2. Click "CONNECT LIVE" (or "USE TESTNET" to practice safely)
3. Go to RULES tab → build your trading rules
4. Go to RISK tab → set your limits
5. Go to AGENT tab → click START AGENT

---

## For Testnet (Practice) Keys
1. Go to https://testnet.binance.vision
2. Login with GitHub
3. Click "Generate HMAC_SHA256 Key"
4. Use those keys with "USE TESTNET" button

---

## How the Agent Works
- Checks your rules every 30 seconds against live Binance prices
- Places real MARKET orders when trigger conditions are met
- Automatically applies stop-loss tracking
- Enforces your risk limits (max trade size, daily loss cap)
- All activity logged in the LOG tab and web dashboard

---

## To Run 24/7 (Optional)
For continuous trading even when your computer is off, deploy the backend to a VPS:

**Option A — PythonAnywhere (free tier)**
1. Sign up at pythonanywhere.com
2. Upload bot.py and requirements.txt
3. Run as a "always-on task"

**Option B — Railway / Render (free tier)**
1. Push code to GitHub
2. Deploy on railway.app or render.com
3. Set environment variables for API keys

**Option C — Cheap VPS ($5/month)**
- DigitalOcean, Vultr, or Hetzner
- Run: `nohup python bot.py &`

---

## Safety Checklist
- [ ] Never enable Withdrawal permissions on API keys
- [ ] Always set a stop-loss on every rule
- [ ] Set a daily loss limit in the RISK tab
- [ ] Test on Testnet before going live
- [ ] Start with small amounts ($10-$50)
- [ ] Never trade money you can't afford to lose

---

## Disclaimer
This software is for educational purposes. Cryptocurrency trading involves substantial risk of loss. Past performance does not guarantee future results. This is not financial advice.
