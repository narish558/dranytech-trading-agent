# DranyTech AI Trading Agent — Local Setup Guide

Run the full app on your computer in 5 minutes.

---

## What You Need
- Python 3.8+ installed
- A web browser (Chrome, Firefox, Edge)
- Your Binance API keys (or testnet keys to practice)
- Your Claude API key (from console.anthropic.com)

---

## STEP 1 — Check Python is Installed

Open your terminal (or Command Prompt on Windows) and type:

```
python --version
```

You should see something like: Python 3.10.x

If not, download Python from: https://python.org/downloads
(Tick "Add Python to PATH" during install on Windows)

---

## STEP 2 — Install the Backend

Open terminal, navigate to the backend folder:

### On Mac/Linux:
```bash
cd /path/to/binance-agent/backend
pip install -r requirements.txt
```

### On Windows:
```cmd
cd C:\path\to\binance-agent\backend
pip install -r requirements.txt
```

You'll see packages installing. Wait for it to finish.

---

## STEP 3 — Start the Backend

In the same terminal, run:

```bash
python bot.py
```

You should see:
```
=======================================================
  Binance Claude AI Agent
  http://localhost:5000
=======================================================
```

**Keep this terminal window open.** The backend must stay running.

---

## STEP 4 — Open the Dashboard

1. Open your file manager
2. Go to the `frontend/` folder
3. Double-click `index.html`
4. It opens in your browser — that's your trading dashboard!

Or in your browser, press Ctrl+O (Cmd+O on Mac) and browse to the file.

---

## STEP 5 — Connect API Keys

In the dashboard SETUP tab:

1. **Binance API Key** — from binance.com → Profile → API Management
2. **Binance Secret Key** — from same place (only shown once!)
3. **Claude API Key** — from console.anthropic.com → API Keys (starts with sk-ant-)
4. **Backend URL** — leave as http://localhost:5000
5. Click **CONNECT LIVE** (or **USE TESTNET** to practice safely)

---

## STEP 6 — Test with Testnet First (Strongly Recommended)

Get free Binance testnet keys:
1. Go to https://testnet.binance.vision
2. Click "Log In with GitHub"
3. Click "Generate HMAC_SHA256 Key"
4. Copy the API Key and Secret Key
5. Paste them in the SETUP tab
6. Click **USE TESTNET**

This lets you test everything with fake money first!

---

## STEP 7 — Add Rules and Start the Agent

1. Go to **RULES** tab → set your first trading rule
   - Example: BUY $100 of BTC/USDT on Spot when Price drops below $80,000
   - Set Stop-Loss: 3%, Take-Profit: 6%

2. Go to **RISK** tab → set your limits
   - Max Trade Size: $100 (start small!)
   - Daily Loss Limit: $50

3. Go to **START AGENT** tab → choose HYBRID mode → click START AGENT

4. Go to **AI AGENT** tab → click ASK CLAUDE NOW to test a live analysis

5. Watch the **LOG** tab to see everything happening in real time

---

## Troubleshooting

**"Cannot reach backend" error:**
- Make sure bot.py is still running in your terminal
- Check the Backend URL is http://localhost:5000
- Try refreshing the browser page

**"Module not found" error when running bot.py:**
- Run: pip install -r requirements.txt again
- Make sure you are in the backend/ folder

**"Auth failed" when connecting:**
- Double-check your API key and secret are correct
- Make sure the API key has Spot/Futures Trading enabled on Binance
- Ensure Withdrawals are DISABLED on the API key

**Page shows nothing / blank:**
- Make sure you opened index.html from the frontend/ folder
- Try a different browser

---

## How to Stop

- To stop the agent: click ■ STOP in the Start Agent tab
- To stop the backend: press Ctrl+C in the terminal

---

## Folder Structure
```
binance-agent/
├── backend/
│   ├── bot.py          ← Run this with "python bot.py"
│   ├── ai_agent.py     ← Claude AI brain (auto-loaded)
│   └── requirements.txt
├── frontend/
│   └── index.html      ← Open this in your browser
├── LOCAL_SETUP.md      ← This guide
└── DEPLOY_TO_RENDER.md ← For cloud deployment later
```

---

## Ready to Deploy to the Cloud?

Once you've tested locally and are happy with how it works,
follow DEPLOY_TO_RENDER.md to run it 24/7 on Render.com.
