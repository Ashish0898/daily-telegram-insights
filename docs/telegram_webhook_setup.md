# Telegram Webhook & Security Setup Guide

To run the bot interactively on Vercel, you need to configure the Telegram webhook URL and set up allowlists and header verification to prevent spam and unauthorized usage.

---

## 1. Webhook Security Environment Variables

Add these variables to your local [.env](file:///mnt/c/Users/Ashish/Downloads/playground/daily-telegram-insights/.env) file and Vercel Project Settings:

| Environment Variable | Description |
| :--- | :--- |
| **`TELEGRAM_WEBHOOK_SECRET`** *(or `TELEGRAM_SECRET_TOKEN`)* | A private custom secret token verified on every incoming Telegram request. |
| **`TELEGRAM_ALLOWED_USER_ID`** | Your personal Telegram user ID to allowlist yourself. |
| **`TELEGRAM_ALLOWED_USER_IDS`** | Comma-separated list of multiple allowed Telegram user IDs. |

---

## 2. Generating a Webhook Secret Token

You must create a secure, random string (like a UUID) to serve as your secret token. This prevents unauthorized HTTP POST requests from triggering your Vercel functions.

You can generate one in your terminal:
```bash
# Using uuidgen
uuidgen

# Or using Python
python3 -c "import uuid; print(uuid.uuid4())"
```

Save this generated token as the `TELEGRAM_WEBHOOK_SECRET` environment variable in Vercel.

---

## 3. Registering the Webhook with Telegram

Inform Telegram's servers where to send update webhooks and supply the secret token:

```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://<your-vercel-host>.vercel.app/api/telegram&secret_token=<YOUR_SECRET_TOKEN>"
```

- Replace `<YOUR_BOT_TOKEN>` with your Telegram token from `@BotFather`.
- Replace `<your-vercel-host>` with your Vercel deployment hostname.
- Replace `<YOUR_SECRET_TOKEN>` with the token generated in Step 2.

---

## 4. How the Allowlist Works

1. **Header Verification**: Every webhook payload from Telegram includes the header `X-Telegram-Bot-Api-Secret-Token`. The bot verifies this matches your `TELEGRAM_WEBHOOK_SECRET`. If it does not match, the request is silently ignored.
2. **User Verification**: When a message is verified, the bot checks the sender's Telegram user ID (`message.from.id`) against your allowlist.
3. **Access Denied**: If the sender is unauthorized, the bot replies with `⚠️ Access Denied - You are not authorized to use this bot` and immediately halts execution to conserve your API/LLM tokens.
