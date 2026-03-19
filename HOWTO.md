# Netflix Code Telegram Bot - Cloudflare Workers Setup

## Prerequisites
- [uv](https://docs.astral.sh/uv/#installation) (Python package manager)
- [Node.js](https://nodejs.org/) (for pywrangler)
- A Google account (the one receiving Netflix emails)
- A Telegram account
- A Cloudflare account

---

## Project Structure

```
netflix-code-bot/
├── src/
│   └── entry.py          # Main worker code
├── pyproject.toml        # Python dependencies
└── wrangler.toml         # Cloudflare config
```

---

## Step 1: Create Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot`
3. Choose a name (e.g., "Netflix Code Bot")
4. Choose a username (e.g., "mynetflix_code_bot")
5. **Copy the Bot Token** - looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

> 💾 Save this as `TELEGRAM_BOT_TOKEN`

---

## Step 2: Get Gmail API Credentials

### 2.1 Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown (top left) → **New Project**
3. Name: `Netflix Code Bot` → **Create**
4. Make sure the new project is selected

### 2.2 Enable Gmail API

1. Go to **APIs & Services** → **Library**
2. Search for **Gmail API**
3. Click on it → **Enable**

### 2.3 Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Select **External** → **Create**
3. Fill in the required fields:
   - App name: `Netflix Code Bot`
   - User support email: `your-email@gmail.com`
   - Developer contact email: `your-email@gmail.com`
4. Click **Save and Continue**
5. **Scopes page**: Click **Save and Continue** (skip this)
6. **Test users page**: 
   - Click **+ Add Users**
   - Add your Gmail address (the one with Netflix emails)
   - Click **Save and Continue**
7. Click **Back to Dashboard**

### 2.4 Create OAuth Credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `Netflix Bot`
5. Under **Authorized redirect URIs**, click **+ Add URI** and enter:
   ```
   https://developers.google.com/oauthplayground
   ```
6. Click **Create**
7. A popup shows your credentials:

> 💾 Save **Client ID** as `GMAIL_CLIENT_ID`
> 💾 Save **Client Secret** as `GMAIL_CLIENT_SECRET`

### 2.5 Get Refresh Token

1. Open [OAuth Playground](https://developers.google.com/oauthplayground/)

2. Click the **⚙️ gear icon** (top right corner)

3. Check ✅ **Use your own OAuth credentials**

4. Enter your credentials:
   - OAuth Client ID: `<your GMAIL_CLIENT_ID>`
   - OAuth Client Secret: `<your GMAIL_CLIENT_SECRET>`

5. Close the settings panel

6. In the left sidebar, scroll to find **Gmail API v1**, expand it

7. Select: `https://www.googleapis.com/auth/gmail.readonly`

8. Click **Authorize APIs** (blue button)

9. Sign in with your Google account (must be the test user you added)

10. Click **Allow** on the consent screen

11. Back in OAuth Playground, click **Exchange authorization code for tokens**

12. In the response on the right, find `refresh_token`

> 💾 Save the **Refresh token** value as `GMAIL_REFRESH_TOKEN`

---

## Step 3: Get Your Telegram User ID (Optional but Recommended)

To restrict the bot so only you can use it:

1. Open Telegram
2. Search for **@userinfobot** and start it
3. It replies with your user ID (a number like `123456789`)

> 💾 Save this as `ALLOWED_USERS`

---

## Step 4: Set Up Cloudflare Worker

### 4.1 Create Project Files

```bash
# Create project directory
mkdir netflix-code-bot
cd netflix-code-bot

# Initialize uv and install dependencies
uv init
uv add httpx
uv tool install workers-py

# Create source directory
mkdir src
```

### 4.2 Create `src/entry.py`

Copy the Python code from the **Netflix Code Bot - Cloudflare Worker (Python)** artifact into `src/entry.py`

### 4.3 Create `wrangler.toml`

Create a file named `wrangler.toml` in the project root:

```toml
name = "netflix-code-bot"
main = "src/entry.py"
compatibility_date = "2024-12-01"
compatibility_flags = ["python_workers"]
```

### 4.4 Update `pyproject.toml`

Make sure your `pyproject.toml` includes:

```toml
[project]
name = "netflix-code-bot"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "httpx>=0.27.0",
]

[tool.uv]
dev-dependencies = [
    "workers-py",
]
```

### 4.5 Login to Cloudflare

```bash
uv run pywrangler login
```

This opens your browser - log in and authorize Wrangler.

### 4.6 Add Secrets

Run each command and paste the corresponding value when prompted:

```bash
uv run pywrangler secret put TELEGRAM_BOT_TOKEN
# Paste your Telegram bot token

uv run pywrangler secret put GMAIL_CLIENT_ID
# Paste your Google OAuth Client ID

uv run pywrangler secret put GMAIL_CLIENT_SECRET
# Paste your Google OAuth Client Secret

uv run pywrangler secret put GMAIL_REFRESH_TOKEN
# Paste your refresh token from OAuth Playground

# Optional: Restrict to your Telegram account only
uv run pywrangler secret put ALLOWED_USERS
# Paste your Telegram user ID (e.g., 123456789)
```

### 4.7 Deploy

```bash
uv run pywrangler deploy
```

**Save the URL** from the output - looks like:
```
https://netflix-code-bot.<your-subdomain>.workers.dev
```

---

## Step 5: Connect Telegram to Your Worker

Set up the webhook by running this command (replace the placeholders):

```bash
curl "https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/setWebhook?url=https://netflix-code-bot.<YOUR_SUBDOMAIN>.workers.dev"
```

**Example:**
```bash
curl "https://api.telegram.org/bot123456789:ABCdefGHI/setWebhook?url=https://netflix-code-bot.john.workers.dev"
```

You should see:
```json
{"ok":true,"result":true,"description":"Webhook was set"}
```

---

## Step 6: Test Your Bot! 🎉

1. Open Telegram
2. Find your bot (search for the username you created)
3. Send `/start` - You should see a welcome message
4. Send `/code` - It will fetch your Netflix verification code!

---

## Summary of All Secrets

| Secret | Value | Where You Got It |
|--------|-------|------------------|
| `TELEGRAM_BOT_TOKEN` | `123456789:ABC...` | BotFather on Telegram |
| `GMAIL_CLIENT_ID` | `xxx.apps.googleusercontent.com` | Google Cloud Console → Credentials |
| `GMAIL_CLIENT_SECRET` | `GOCSPX-xxx` | Google Cloud Console → Credentials |
| `GMAIL_REFRESH_TOKEN` | `1//0xxx` | OAuth Playground |
| `ALLOWED_USERS` | `123456789` | @userinfobot on Telegram |

---

## Troubleshooting

### "Failed to authenticate with Gmail"
- Double-check `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, and `GMAIL_REFRESH_TOKEN`
- Make sure Gmail API is enabled in Google Cloud Console
- Verify your email is added as a test user in OAuth consent screen

### "No Netflix emails found"
- Check that Netflix emails aren't going to spam
- Only emails from the last 24 hours are searched
- Make sure you're checking the correct Gmail account

### Bot not responding
- Verify webhook is set: 
  ```bash
  curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
  ```
- Check worker logs:
  ```bash
  uv run pywrangler tail
  ```

### "You are not authorized"
- Your Telegram user ID isn't in `ALLOWED_USERS`
- Remove the `ALLOWED_USERS` secret to allow anyone, or add your ID

---

## Useful Commands

```bash
# View real-time logs
uv run pywrangler tail

# Redeploy after code changes
uv run pywrangler deploy

# Update a secret
uv run pywrangler secret put SECRET_NAME

# Delete a secret
uv run pywrangler secret delete SECRET_NAME

# Test locally
uv run pywrangler dev
```

---

## Cost

✅ **Free!** Cloudflare Workers free tier includes:
- 100,000 requests per day
- No cold starts for Python Workers

Your bot will likely use only a few requests per day.