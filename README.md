# Daily Fact & News Telegram Bot

Automatically send a daily random fact and dynamic web news updates to Telegram using GitHub LLM API and Talivy Search.

## Features

- 🤖 **Random Facts**: Generates unique, highly interesting facts using GitHub's LLM API (`openai/gpt-4.1-nano`).
- 📡 **Dynamic News Digest**: Dynamically generates a fresh news search query every day (e.g., in fields like AI, space, science) using the LLM, then fetches live updates using the Talivy Search API. Fallbacks to `"world news at a glance today"`.
- 🔒 **Webhook Security Middleware**:
  - **Secret Token Verification**: Authenticates incoming requests from Telegram using a secret webhook token.
  - **User Allowlisting**: Restricts bot access to specific Telegram user IDs. Responds to unauthorized users with a clean Access Denied message and halts processing immediately to save API quotas.
- ⚡ **Minimal dependencies & high speed** for low execution overhead.
- 🧪 **Scheduled or Manual triggers** via GitHub Actions or Vercel Crons.

---

## Setup

### 1. Create GitHub Secrets (for GitHub Actions)

If running facts via GitHub Actions, add these secrets (Settings → Secrets and variables → Actions):

- `GITHUB_TOKEN` - Your GitHub API key for LLM access
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token (from @BotFather)
- `TELEGRAM_CHAT_ID` - Your Telegram chat/user ID

---

## Interactive Telegram bot with Vercel

The bot can run as an interactive serverless webhook handler on Vercel.

### Deploy the webhook endpoint

Create a Vercel project from this repository and add these environment variables:

#### Core Config
- `GITHUB_TOKEN` - Your GitHub API key for LLM access
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your default Telegram chat ID (for scheduled messages)

#### Webhook Security (Recommended)
- `TELEGRAM_WEBHOOK_SECRET` (or `TELEGRAM_SECRET_TOKEN`) - A custom secret string (like a UUID) to authenticate incoming requests from Telegram.
- `TELEGRAM_ALLOWED_USER_ID` - Your personal Telegram user ID to allowlist yourself.
- `TELEGRAM_ALLOWED_USER_IDS` - Comma-separated list of multiple allowed Telegram user IDs (alternative/addition to the above).

#### Talivy Search Config
- `TALIVY_API_KEY` - Your Talivy API key
- `TALIVY_ENDPOINT` - Talivy search endpoint URL
- `NEWS_QUERY` (optional) - Overrides the LLM-generated dynamic query with a fixed query
- `NEWS_LIMIT` (optional) - Number of news results to fetch (default: `5`)
- `NEWS_SUMMARY` (optional) - Set to `true` to deliver as a single summary message instead of separate posts

---

### Security Configuration

#### 1. Generate a Webhook Secret Token
You can generate a secure UUID string to use as your secret token:
```bash
# In your terminal
uuidgen
# Or via Python
python3 -c "import uuid; print(uuid.uuid4())"
```
Set this generated string as the `TELEGRAM_WEBHOOK_SECRET` environment variable in Vercel.

#### 2. Set the Telegram Webhook with Secret Token
Point Telegram to your Vercel deployment URL and include the `secret_token` parameter:
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<your-vercel-host>.vercel.app/api/telegram&secret_token=<YOUR_SECRET_TOKEN>"
```

#### 3. How the Allowlist Works
* If any allowlist variable (`TELEGRAM_ALLOWED_USER_ID`, `TELEGRAM_ALLOWED_USER_IDS`, or `TELEGRAM_CHAT_ID` if positive) is set, the bot will verify the sender's Telegram user ID (`message.from.id`).
* If an unauthorized user attempts to message the bot, it replies with `⚠️ Access Denied\n\nYou are not authorized to use this bot.` and immediately terminates execution.
* If a request does not contain the correct `X-Telegram-Bot-Api-Secret-Token` header, it is rejected silently to prevent spam/reconnaissance.

---

### Vercel schedules

Vercel will automatically run the scheduled endpoints defined in `vercel.json`:

- `GET /api/fact` — send a daily fact
- `GET /api/news` — send a daily dynamic news update

---

### Available bot commands

- `/fact` — send a new random fact
- `/news` — generate a dynamic news query via LLM and search Talivy
- `/news <query>` — search Talivy for a specific query
- `/search <query>` — search Talivy for a custom topic
- `/help` — show help text

---

## Local Testing

To test the LLM fact generation locally:
```bash
export GITHUB_TOKEN="your_key"
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

python src/generate_fact.py
```

To test the news generation locally (uses the dynamic LLM topic query by default, or defaults to world news fallback):
```bash
export GITHUB_TOKEN="your_key"
export TALIVY_API_KEY="your_talivy_key"
export TALIVY_ENDPOINT="https://api.talivy.example/search"

# Runs with dynamic news topic query
python src/send_news.py

# Runs with custom query
python src/send_news.py --query "latest football news"
```

## License

MIT
