"""
Netflix Code Telegram Bot - Cloudflare Workers Python
Fetches Netflix verification codes from Gmail via REST API.

Environment Variables (Secrets):
    TELEGRAM_BOT_TOKEN - Your Telegram bot token from @BotFather
    GMAIL_REFRESH_TOKEN - OAuth2 refresh token for Gmail
    GMAIL_CLIENT_ID - Google OAuth2 client ID
    GMAIL_CLIENT_SECRET - Google OAuth2 client secret
    ALLOWED_USERS - Comma-separated Telegram user IDs (optional)
"""

import re
import base64
import json
from datetime import datetime, timezone
from urllib.parse import urlencode

from workers import WorkerEntrypoint, Response
import httpx


# Gmail API endpoints
GMAIL_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

# Netflix sender emails
NETFLIX_SENDERS = ["info@account.netflix.com", "info@netflix.com"]


def extract_netflix_code(text: str) -> str | None:
    """Extract 6-digit Netflix verification code from email text."""
    patterns = [
        r'\b(\d{6})\b',
        r'code[:\s]+(\d{6})',
        r'verification[:\s]+(\d{6})',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def decode_base64url(data: str) -> str:
    """Decode base64url encoded string."""
    padding = 4 - len(data) % 4
    if padding != 4:
        data += "=" * padding
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")


def get_email_body(payload: dict) -> str:
    """Extract email body from Gmail API payload."""
    body = ""
    
    if "body" in payload and payload["body"].get("data"):
        body = decode_base64url(payload["body"]["data"])
    
    if "parts" in payload:
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            if mime_type == "text/plain" and part.get("body", {}).get("data"):
                body += decode_base64url(part["body"]["data"])
            elif mime_type == "text/html" and part.get("body", {}).get("data"):
                html_body = decode_base64url(part["body"]["data"])
                clean_text = re.sub(r'<[^>]+>', ' ', html_body)
                body += clean_text
            elif "parts" in part:
                body += get_email_body(part)
    
    return body


class Default(WorkerEntrypoint):
    """Main Cloudflare Worker entrypoint."""
    
    async def get_access_token(self, env) -> str | None:
        """Get a fresh access token using refresh token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                GMAIL_TOKEN_URL,
                data={
                    "client_id": env.GMAIL_CLIENT_ID,
                    "client_secret": env.GMAIL_CLIENT_SECRET,
                    "refresh_token": env.GMAIL_REFRESH_TOKEN,
                    "grant_type": "refresh_token",
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("access_token")
            return None
    
    async def fetch_netflix_code(self, env) -> tuple[str | None, str]:
        """Fetch the latest Netflix verification code from Gmail."""
        access_token = await self.get_access_token(env)
        if not access_token:
            return None, "Failed to authenticate with Gmail. Check your credentials."
        
        async with httpx.AsyncClient() as client:
            # Build search query for Netflix emails
            senders_query = " OR ".join([f"from:{s}" for s in NETFLIX_SENDERS])
            query = f"({senders_query}) newer_than:1d"
            
            # Search for messages
            params = urlencode({"q": query, "maxResults": "5"})
            response = await client.get(
                f"{GMAIL_API_BASE}/messages?{params}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            
            if response.status_code != 200:
                return None, f"Gmail API error: {response.status_code}"
            
            data = response.json()
            messages = data.get("messages", [])
            
            if not messages:
                return None, "No Netflix emails found in the last 24 hours."
            
            # Check each message for a verification code
            for msg_info in messages:
                msg_response = await client.get(
                    f"{GMAIL_API_BASE}/messages/{msg_info['id']}?format=full",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                
                if msg_response.status_code != 200:
                    continue
                
                msg = msg_response.json()
                headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
                subject = headers.get("Subject", "")
                
                # Check if this looks like a verification email
                keywords = ["code", "verification", "verify", "sign in", "login", "temporary"]
                if any(kw in subject.lower() for kw in keywords):
                    body = get_email_body(msg["payload"])
                    code = extract_netflix_code(body)
                    
                    if code:
                        # Calculate time ago
                        internal_date = int(msg.get("internalDate", 0)) / 1000
                        email_time = datetime.fromtimestamp(internal_date, tz=timezone.utc)
                        now = datetime.now(tz=timezone.utc)
                        time_diff = (now - email_time).total_seconds()
                        
                        if time_diff < 60:
                            time_str = "just now"
                        elif time_diff < 3600:
                            time_str = f"{int(time_diff // 60)} minutes ago"
                        else:
                            time_str = f"{int(time_diff // 3600)} hours ago"
                        
                        return code, f"Found in: '{subject}' ({time_str})"
            
            return None, "No verification code found in recent Netflix emails."
    
    async def send_telegram_message(self, env, chat_id: int, text: str, parse_mode: str = "Markdown"):
        """Send a message via Telegram Bot API."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{env.TELEGRAM_BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
    
    async def edit_telegram_message(self, env, chat_id: int, message_id: int, text: str, parse_mode: str = "Markdown"):
        """Edit a Telegram message."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"https://api.telegram.org/bot{env.TELEGRAM_BOT_TOKEN}/editMessageText",
                json={
                    "chat_id": chat_id,
                    "message_id": message_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
    
    def is_user_allowed(self, env, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        allowed_users = getattr(env, "ALLOWED_USERS", None)
        if not allowed_users:
            return True  # No restriction if not configured
        
        allowed_list = [int(uid.strip()) for uid in allowed_users.split(",") if uid.strip()]
        return user_id in allowed_list
    
    async def handle_telegram_update(self, env, update: dict):
        """Handle incoming Telegram update."""
        message = update.get("message", {})
        text = message.get("text", "")
        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        
        if not chat_id:
            return
        
        # Check if user is allowed
        if not self.is_user_allowed(env, user_id):
            await self.send_telegram_message(
                env, chat_id,
                "⛔ You are not authorized to use this bot."
            )
            return
        
        # Handle /start command
        if text.startswith("/start"):
            welcome = (
                "👋 *Welcome to Netflix Code Bot!*\n\n"
                "I fetch Netflix verification codes from your Gmail.\n\n"
                "*Commands:*\n"
                "/code - Get the latest Netflix verification code\n"
                "/help - Show this help message"
            )
            await self.send_telegram_message(env, chat_id, welcome)
        
        # Handle /help command
        elif text.startswith("/help"):
            help_text = (
                "📖 *Netflix Code Bot Help*\n\n"
                "`/code` - Fetches the most recent Netflix verification code\n\n"
                "The bot searches Gmail for Netflix emails from the last 24 hours "
                "and extracts the 6-digit verification code."
            )
            await self.send_telegram_message(env, chat_id, help_text)
        
        # Handle /code command
        elif text.startswith("/code"):
            # Send searching message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.telegram.org/bot{env.TELEGRAM_BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": chat_id,
                        "text": "🔍 Searching for Netflix verification code...",
                    },
                )
                sent_msg = response.json().get("result", {})
                message_id = sent_msg.get("message_id")
            
            # Fetch the code
            code, info = await self.fetch_netflix_code(env)
            
            if code:
                result_text = (
                    f"✅ *Netflix Verification Code*\n\n"
                    f"`{code}`\n\n"
                    f"📧 {info}"
                )
            else:
                result_text = f"❌ {info}"
            
            # Edit the message with result
            if message_id:
                await self.edit_telegram_message(env, chat_id, message_id, result_text)
            else:
                await self.send_telegram_message(env, chat_id, result_text)
    
    async def fetch(self, request, env):
        """Handle incoming HTTP requests."""
        # Handle Telegram webhook
        if request.method == "POST":
            try:
                body = await request.json()
                await self.handle_telegram_update(env, body)
                return Response("OK", status=200)
            except Exception as e:
                return Response(f"Error: {str(e)}", status=500)
        
        # Handle GET request (for webhook setup verification)
        if request.method == "GET":
            return Response("Netflix Code Bot is running! 🎬", status=200)
        
        return Response("Method not allowed", status=405)