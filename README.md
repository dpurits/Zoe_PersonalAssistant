# Zoe Personal Assistant

Personal WhatsApp assistant for calendar, Gmail, daily briefings, and weekly finance research.

## V1 Scope

- Chat through Twilio WhatsApp Sandbox.
- Understand and respond in English and Hebrew.
- Read Google Calendar and Gmail after OAuth authorization.
- Create Gmail drafts only.
- Create calendar events only after explicit confirmation.
- Send a daily morning brief at 07:45 Asia/Jerusalem.
- Send a Sunday finance review covering Israel, US, China, Japan, and EU markets.
- Keep an audit trail for assistant actions.

## Local Setup

1. Create a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies.

```powershell
pip install -e ".[dev]"
```

3. Copy environment variables.

```powershell
Copy-Item .env.example .env
```

4. Run the API.

```powershell
uvicorn zoe_assistant.main:app --reload
```

5. Expose the webhook for Twilio local testing.

```powershell
ngrok http 8000
```

Use the public URL in Twilio as:

```text
https://YOUR_NGROK_DOMAIN/twilio/whatsapp
```

## Useful Endpoints

- `GET /health` - basic health check.
- `POST /twilio/whatsapp` - Twilio WhatsApp inbound webhook.
- `POST /assistant/chat` - local JSON chat test endpoint.
- `GET /google/oauth/start` - begin Google OAuth.
- `GET /google/oauth/status` - check whether Google is connected.
- `GET /google/calendar/events` - list upcoming Google Calendar events.
- `GET /google/gmail/search?q=from:someone@example.com` - search Gmail.
- `GET /briefings/daily/preview` - compose a daily brief from Google data.
- `GET /portfolio/watchlist` - configured finance watchlist.

## Google OAuth Setup

1. Generate a token encryption key and put it in `.env`.

```powershell
.\.venv\Scripts\python.exe scripts\generate_fernet_key.py
```

2. In Google Cloud Console:

- Enable Gmail API.
- Enable Google Calendar API.
- Configure OAuth consent screen.
- Add yourself as a test user while the app is in testing.
- Create OAuth client credentials of type `Web application`.
- Add this authorized redirect URI for local dev:

```text
http://localhost:8000/google/oauth/callback
```

3. Fill these values in `.env`:

```text
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/google/oauth/callback
TOKEN_ENCRYPTION_KEY=
```

4. Start the API and open:

```text
http://localhost:8000/google/oauth/start
```

## Render Deployment

### Free Prototype Path

Use a plain Render **Web Service** instead of a Blueprint. The Blueprint/database path can request payment details because it provisions additional resources.

Tradeoff: this free path uses file-based encrypted token storage on the Render instance. If Render redeploys or restarts the instance, you might need to reconnect Google OAuth. For persistent production use, switch `TOKEN_STORE=database` and add Postgres later.

1. Push this repo to GitHub.
2. In Render, create a new **Web Service** from the GitHub repo.
3. Choose the free instance type.
4. Set:

```text
Build Command: pip install -e .
Start Command: uvicorn zoe_assistant.main:app --host 0.0.0.0 --port $PORT
```

5. Add the required secret environment variables in the Render dashboard:

```text
APP_ENV=production
TIMEZONE=Asia/Jerusalem
TOKEN_STORE=file
TOKEN_ENCRYPTION_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=https://YOUR-RENDER-SERVICE.onrender.com/google/oauth/callback
OPENAI_API_KEY=
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886
PRIMARY_WHATSAPP_TO=whatsapp:+YOUR_PHONE_NUMBER
```

6. In Google Cloud Console, add this Authorized redirect URI to the same OAuth client:

```text
https://YOUR-RENDER-SERVICE.onrender.com/google/oauth/callback
```

7. After Render deploys, connect Google by opening:

```text
https://YOUR-RENDER-SERVICE.onrender.com/google/oauth/start
```

8. In Twilio WhatsApp Sandbox, set `When a message comes in` to:

```text
https://YOUR-RENDER-SERVICE.onrender.com/twilio/whatsapp
```

Use method `POST`.

## Safety Defaults

- Email sending is disabled.
- Email deletion, archive, and labeling are disabled.
- Gmail draft creation is allowed after Google OAuth is configured.
- Calendar event creation requires explicit confirmation.
- Financial summaries are research only, not investment advice.
