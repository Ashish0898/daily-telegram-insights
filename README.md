# Daily Fact & News Telegram Bot

Automatically send a daily random fact and dynamic web news updates to Telegram using GitHub LLM API and Talivy Search.

## Features

- 🤖 **Random Facts**: Generates unique, highly interesting facts using GitHub's LLM API (`openai/gpt-4.1-nano`).
- 📡 **Dynamic News Digest**: Dynamically generates a fresh news search query every day (e.g., in fields like AI, space, science) using the LLM, then fetches live updates using the Talivy Search API. Fallbacks to `"world news at a glance today"`.
- 🔒 **Webhook Security Middleware**:
  - **Secret Token Verification**: Authenticates incoming requests from Telegram using a secret webhook token.
  - **User Allowlisting**: Restricts bot access to specific Telegram user IDs. Responds to unauthorized users with a clean Access Denied message and halts processing immediately to save API quotas.
- 📊 **Request Auditing**: Logs execution statistics, query topics, bot responses, and performance metrics directly to a Supabase database. See [Supabase Setup Guide](docs/supabase_setup.md) for details.
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

### Deploy the Webhook Endpoint

Create a Vercel project from this repository and add your environment variables.

#### Core Configuration
- `GITHUB_TOKEN` - Your GitHub API key for LLM access.
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token (from @BotFather).
- `TELEGRAM_CHAT_ID` - Your default Telegram chat ID (used for scheduled messages).

#### Webhook Security & Access Control
All instructions to generate a webhook secret token, register webhook URLs, and configure user allowlists have been moved to the **[Telegram Webhook & Security Setup Guide](docs/telegram_webhook_setup.md)**.

#### Talivy Search Configuration
To query live news digests and custom searches using the Talivy API, refer to the **[Talivy Search Integration Guide](docs/talivy_setup.md)** for configuration details.

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
- `/allow <user_id> [role] [username]` — allow a user to access the bot (admin only)
- `/revoke <user_id>` — revoke access for a user (admin only)
- `/help` — show help text

---

## Request Auditing (Supabase)

The bot logs all webhook inputs, scheduled triggers, response contents, and performance metrics to a Supabase database for tracking and analytics.

To set up request auditing:
1. Follow the database schema and configurations in [Supabase Setup Guide](docs/supabase_setup.md).
2. Set the `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` environment variables.

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
