# Daily Fact GitHub Action

Automatically send a daily random fact to Telegram using GitHub LLM API.

## Features

- 🤖 Generates random facts using GitHub's LLM API
- 🌐 Optional Talivy web search support for live news updates
- 📱 Sends to Telegram daily at 7:00 AM IST
- ⚡ Minimal dependencies for fast execution
- 💚 Energy-efficient with pip caching
- 🧪 Manual trigger support for testing

## Setup

### 1. Create GitHub Secrets

Add these secrets to your repository (Settings → Secrets and variables → Actions):

- `GITHUB_TOKEN` - Your GitHub API key for LLM access
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token (from @BotFather)
- `TELEGRAM_CHAT_ID` - Your Telegram chat/user ID

Optional Talivy secrets for web search updates:

- `TALIVY_API_KEY` - Your Talivy API key
- `TALIVY_ENDPOINT` - Talivy search endpoint URL

### 2. Get Telegram Credentials

1. Create a bot with [@BotFather](https://t.me/botfather)
2. Get your chat ID:
   - Send a message to your bot
   - Visit `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
   - Find your `chat.id` in the JSON response

### 3. Local Testing

```bash
export GITHUB_TOKEN="your_key"
export TELEGRAM_BOT_TOKEN="your_token"
export TELEGRAM_CHAT_ID="your_chat_id"

python src/generate_fact.py
```

## Optional: Talivy web search support

If you want the bot to fetch web updates like latest football news, add these secrets:

- `TALIVY_API_KEY` - Your Talivy API key
- `TALIVY_ENDPOINT` - Talivy search endpoint URL

Then run:

```bash
export TALIVY_API_KEY="your_talivy_key"
export TALIVY_ENDPOINT="https://api.talivy.example/search"
python src/send_news.py --query "latest football news"
```

For Telegram delivery, this will send the search summary to the same chat configured by `TELEGRAM_CHAT_ID`.

## Configuration

- **Schedule**: Edit `.github/workflows/daily-fact.yml` to change the cron schedule
  - Current: 7:00 AM IST (1:30 AM UTC)
  - Format: `minute hour * * *` (UTC timezone)
- **Fact style**: Modify the system prompt in `src/generate_fact.py`
- **Message format**: Edit the message template with emoji/title

## Manual Trigger

You can manually trigger the workflow from the GitHub Actions tab for testing.

## Performance

- Dependencies: 1 (requests)
- First run: ~2-3 seconds
- Subsequent runs: <1 second (with pip caching)
- API calls: 2 (GitHub LLM + Telegram)

## License

MIT
