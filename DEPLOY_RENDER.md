# Deploy to Render.com (Free Tier - WebSocket Enabled)

## Why Render.com?
- ✅ **WebSocket WORKS** - unlike HuggingFace Spaces
- ✅ **Free tier** available (spins down after 15 min inactivity)
- ✅ **HTTPS included** automatically
- ✅ **Python 3.11** supported

---

## Step 1: Prepare Your Code

All files are already created:
- `Procfile` - Tells Render how to run your app
- `runtime.txt` - Specifies Python version
- `.env.example` - Template for environment variables

---

## Step 2: Push Code to GitHub

```bash
# In your project directory
cd C:\Users\Admin\Desktop\algo\algo

# Initialize git if not done
git init
git add .
git commit -m "Ready for Render.com deployment"

# Create a new repository on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

---

## Step 3: Create Render Account

1. Go to https://render.com
2. Sign up with GitHub
3. Click "New +" → "Web Service"

---

## Step 4: Connect GitHub Repository

1. Select your repository
2. Settings:
   - **Name**: `kite-algo` (or any name)
   - **Branch**: `main`
   - **Runtime**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn streaming_api:app --host 0.0.0.0 --port $PORT`

---

## Step 5: Add Environment Variables

Click "Advanced" → Add these secrets:

| Variable | Value |
|----------|-------|
| `KITE_API_KEY` | Your Kite API Key |
| `KITE_API_SECRET` | Your Kite API Secret |
| `KITE_ACCESS_TOKEN` | Your Access Token (run `python refresh_token.py`) |
| `KITE_USER_ID` | Your Kite User ID |
| `KITE_PASSWORD` | Your Kite Password |
| `KITE_TOTP_SECRET` | Your TOTP Secret |
| `RENDER` | `true` |

---

## Step 6: Deploy

1. Click "Create Web Service"
2. Wait 3-5 minutes for build
3. Check logs for any errors

---

## Step 7: Access Your API

After deployment, you'll get a URL like:
```
https://kite-algo.onrender.com
```

Test it:
```bash
curl https://kite-algo.onrender.com/api/health
curl https://kite-algo.onrender.com/api/all-futures-combined
```

---

## Important Notes

### Free Tier Limitations
- Service **spins down after 15 minutes** of no traffic
- First request after inactivity takes ~1 minute to start
- WebSocket will reconnect automatically when service wakes up

### Keep Service Awake (Optional)
Use a free uptime monitor like https://uptimerobot.com to ping every 14 minutes:
```
https://kite-algo.onrender.com/api/health
```

### Token Refresh
The app will automatically refresh your token hourly. Make sure `KITE_TOTP_SECRET` is set correctly!

---

## Troubleshooting

**WebSocket not connecting?**
- Check logs in Render dashboard
- Ensure `RENDER=true` is set in environment variables

**Token expired?**
- Run `python refresh_token.py` locally to get new token
- Update `KITE_ACCESS_TOKEN` in Render env vars

**Build failed?**
- Check Python version in `runtime.txt`
- Ensure all dependencies in `requirements.txt` are correct

---

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | API info |
| `/api/health` | Health check |
| `/api/all-futures-combined` | All futures data |
| `/api/live-data` | Live spot prices |
| `/api/near-futures` | Near futures |
| `/api/next-futures` | Next futures |
| `/api/far-futures` | Far futures |
| `/api/stream` | SSE real-time stream |
| `/api/websocket/retry` | Retry WebSocket |
