# Render Deployment Guide
## Binance Claude AI Trading Agent — Live in 10 Minutes

---

## What You Need Before Starting
- [ ] GitHub account (free) — github.com
- [ ] Render account (free) — render.com
- [ ] Binance API key + Secret
- [ ] Claude API key (from console.anthropic.com)

---

## STEP 1 — Push Code to GitHub (5 minutes)

### Option A: GitHub Desktop (Easiest — No Command Line)
1. Download GitHub Desktop from https://desktop.github.com
2. Open it → Sign in to your GitHub account
3. Click **File → Add Local Repository**
4. Browse to your `binance-agent` folder → click **Add Repository**
5. If it says "not a git repo" → click **Create Repository**
6. Give it a name: `binance-ai-agent`
7. Click **Publish Repository** (top right)
8. Make sure "Keep this code private" is checked ✓
9. Click **Publish Repository**
10. Your code is now on GitHub!

### Option B: Command Line
```bash
cd binance-agent

# Initialize git
git init
git add .
git commit -m "Initial commit: Binance Claude AI Agent"

# Create repo on GitHub (go to github.com → New Repository)
# Then connect and push:
git remote add origin https://github.com/YOUR_USERNAME/binance-ai-agent.git
git branch -M main
git push -u origin main
```

---

## STEP 2 — Deploy to Render (5 minutes)

1. Go to **https://render.com** and sign up (free)
2. Click **"New +"** → select **"Web Service"**
3. Click **"Connect a Repository"**
4. Authorize Render to access GitHub → select your `binance-ai-agent` repo
5. Fill in these settings:

| Field | Value |
|-------|-------|
| Name | `binance-claude-agent` |
| Region | Oregon (US West) or Frankfurt |
| Branch | `main` |
| Root Directory | `backend` |
| Runtime | `Python 3` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python bot.py` |
| Instance Type | **Starter ($7/month)** ← important for 24/7 |

> ⚠️ Free tier sleeps after 15min inactivity. Use Starter for always-on trading.

---

## STEP 3 — Add Your API Keys as Environment Variables

**This is the most important step — never put keys in code files.**

In Render dashboard → your service → **Environment** tab → click **Add Environment Variable**:

| Key | Value |
|-----|-------|
| `BINANCE_API_KEY` | Your Binance API key |
| `BINANCE_API_SECRET` | Your Binance Secret key |
| `ANTHROPIC_API_KEY` | Your Claude API key (sk-ant-...) |
| `TESTNET` | `false` (or `true` for testnet) |

Click **Save Changes** → Render will auto-redeploy.

---

## STEP 4 — Get Your Live Backend URL

After deployment (takes ~2 minutes):
1. Go to your Render service dashboard
2. At the top you'll see a URL like:
   `https://binance-claude-agent.onrender.com`
3. Copy this URL — this is your backend address

Test it by visiting:
`https://binance-claude-agent.onrender.com/status`

You should see:
```json
{"connected": true, "has_ai": true, ...}
```

---

## STEP 5 — Connect Your Frontend Dashboard

Open `frontend/index.html` in your browser (just double-click it locally).

In the SETUP tab:
1. **Backend URL** → paste your Render URL:
   `https://binance-claude-agent.onrender.com`
2. Leave API keys blank (they're already in Render env vars)
3. Click **CONNECT LIVE**

Your dashboard is now talking to your live cloud agent!

---

## STEP 6 — Host Frontend on GitHub Pages (Optional)

To access your dashboard from anywhere (phone, other computer):

1. In your GitHub repo → go to **Settings → Pages**
2. Source: **Deploy from a branch**
3. Branch: `main` / folder: `/ (root)`
4. Save → wait 2 minutes
5. Your dashboard will be at:
   `https://YOUR_USERNAME.github.io/binance-ai-agent/frontend/`

Update the Backend URL in the dashboard to your Render URL.

---

## STEP 7 — Start the Agent

1. Open your dashboard (local or GitHub Pages)
2. Go to **RULES** tab → add your first trading rules
3. Go to **RISK** tab → set your limits
4. Go to **START AGENT** tab → select mode → click **▶ START AGENT**
5. Go to **AI AGENT** tab → click **◉ ASK CLAUDE NOW** to test a manual analysis
6. Go to **LOG** tab → watch real-time activity

---

## Auto-Restart After Deploy

Every time you push new code to GitHub, Render automatically:
- Pulls your latest code
- Rebuilds and restarts the agent
- Your environment variables stay safe

---

## Monitoring & Alerts

Render free monitoring:
- Go to your service → **Metrics** tab → see CPU, memory, requests
- Go to **Logs** tab → see your bot's real-time console output (same as LOG tab in dashboard)
- Set up email alerts: **Settings → Notifications**

---

## Cost Summary

| Plan | Price | Good For |
|------|-------|---------|
| Free | $0 | Testing only (sleeps after 15min) |
| Starter | $7/month | 24/7 trading — recommended |
| Standard | $25/month | High-frequency trading |

---

## Troubleshooting

**Agent won't connect:**
- Check your API keys are correct in Render env vars
- Make sure Render service is running (green dot in dashboard)
- Visit `https://your-app.onrender.com/status` to check

**"Module not found" error:**
- Check `requirements.txt` has all packages
- Trigger a manual redeploy in Render dashboard

**Trades not executing:**
- Check LOG tab for error messages
- Verify Binance API key has Spot/Futures Trading enabled
- Check risk settings — max trade size may be blocking orders

**Free tier sleeping:**
- Upgrade to Starter ($7/mo) for always-on
- Or use a free uptime monitor like UptimeRobot to ping your app every 5 minutes

---

## Security Checklist
- [ ] Repo is set to **Private** on GitHub
- [ ] API keys are ONLY in Render environment variables, never in code
- [ ] Binance API key has Withdrawals DISABLED
- [ ] IP whitelist set on Binance API key (add Render's IP)
- [ ] Daily loss limit configured in Risk tab
- [ ] Tested on Testnet before going live

---

*Your agent will now run 24/7 in the cloud, analyzing markets with Claude AI
and executing trades automatically — even while you sleep.*
