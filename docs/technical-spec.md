# Technical Spec

## Product Goal

Zoe is a private personal assistant reachable through WhatsApp. It can read approved data sources, summarize what matters, draft replies, and create calendar events after confirmation.

## Initial Decisions

- Backend language: Python.
- API framework: FastAPI.
- Chat provider: Twilio WhatsApp Sandbox for V1.
- Deployment: Render.
- Personal data provider: Google first, Outlook later.
- Supported languages: English and Hebrew.
- Timezone: Asia/Jerusalem.
- Daily brief time: 07:45.
- Email write capability: Gmail draft creation only.
- Calendar write capability: confirmation required.

## Main Components

### WhatsApp Gateway

Receives inbound Twilio webhook requests and returns a WhatsApp reply. Later, scheduled jobs will send outbound WhatsApp messages through Twilio REST.

### Assistant Orchestrator

Interprets user intent, selects tools, and returns responses. The first implementation has a simple deterministic shell. The next version will connect OpenAI tool calling to the service layer.

### Google Services

Google OAuth will request the minimum scopes needed for:

- Calendar read.
- Calendar event creation.
- Gmail read/search.
- Gmail draft creation.

Sending email is intentionally out of scope for V1.

### Scheduler

APScheduler runs:

- Daily brief at 07:45 Asia/Jerusalem.
- Sunday finance review at a configured time.

For later multi-user support, scheduled jobs should move to a persistent queue or worker.

### Finance Research

The finance module starts with a watchlist extracted from the provided screenshots. It should separate:

- Portfolio/watchlist monitoring.
- Market index overview.
- Candidate discovery.
- News and earnings context.

Every financial report must be framed as research, not advice.

## Safety Rules

- Never send email in V1.
- Never delete, archive, or label email in V1.
- Never execute trades.
- Ask for confirmation before creating calendar events.
- Log all tool calls and proposed actions.
- Store OAuth tokens encrypted at rest.

## Later Expansion

- Add Outlook/Microsoft Graph for work calendar and email.
- Add wife/family multi-user support with separate OAuth connections.
- Add user-specific permissions and preferences.
- Add richer financial data providers.
- Add monitoring and alerting.

