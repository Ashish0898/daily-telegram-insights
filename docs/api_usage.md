# Bot API & Webhook Usage Guide

This guide describes how to run the unified local server and test the webhook and scheduler API endpoints using `curl` commands.

---

## 1. Running the API Server Locally

To test endpoints locally, you can start the built-in HTTP server:

```bash
# Set required environment variables
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export GEMINI_API_KEY="your_gemini_api_key"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
export TALIVY_API_KEY="your_talivy_key"

# (Optional) Set up database connection to test Supabase
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-supabase-service-role-key"

# (Optional) Webhook Secret Token for security
export TELEGRAM_WEBHOOK_SECRET="my-super-secret-token"

# Start the unified local server (runs on port 3000 by default)
python3 api/index.py
```

---

## 2. Webhook Endpoint (`POST /api/telegram`)

The bot webhook accepts Telegram update payloads. When testing locally, you can simulate user commands.

### Header Authentication
If `TELEGRAM_WEBHOOK_SECRET` is set in the environment, you must include the matching secret token in the request header:
`X-Telegram-Bot-Api-Secret-Token: <your_secret_token>`

### A. Simulate `/start` Command (New User Registration)
This simulates a user who is not in the database launching the bot. If not listed in the environment variable allowlist, they will be registered in Supabase as an inactive user (`is_active = False`) and receive an access denied response with their numeric user ID.

```bash
curl -X POST http://localhost:3000/api/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: my-super-secret-token" \
  -d '{
    "message": {
      "message_id": 100,
      "from": {
        "id": 999999999,
        "is_bot": false,
        "first_name": "Alice",
        "username": "alice_test"
      },
      "chat": {
        "id": 999999999,
        "first_name": "Alice",
        "type": "private"
      },
      "date": 1623652800,
      "text": "/start"
    }
  }'
```

### B. Simulate `/fact` Command
Simulates an authorized user requesting a random daily fact.

```bash
curl -X POST http://localhost:3000/api/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: my-super-secret-token" \
  -d '{
    "message": {
      "message_id": 101,
      "from": {
        "id": 123456789,
        "is_bot": false,
        "first_name": "John",
        "username": "johndoe"
      },
      "chat": {
        "id": 123456789,
        "first_name": "John",
        "type": "private"
      },
      "date": 1623652800,
      "text": "/fact"
    }
  }'
```

### C. Simulate `/news` Command with Custom Query
Simulates a user requesting news on a custom topic (e.g. quantum computing).

```bash
curl -X POST http://localhost:3000/api/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: my-super-secret-token" \
  -d '{
    "message": {
      "message_id": 102,
      "from": {
        "id": 123456789,
        "is_bot": false,
        "first_name": "John",
        "username": "johndoe"
      },
      "chat": {
        "id": 123456789,
        "first_name": "John",
        "type": "private"
      },
      "date": 1623652800,
      "text": "/news artificial intelligence"
    }
  }'
```

### D. Simulate Admin Command `/allow`
Simulates an administrator allowing access for a user using their username.

```bash
curl -X POST http://localhost:3000/api/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: my-super-secret-token" \
  -d '{
    "message": {
      "message_id": 103,
      "from": {
        "id": 123456789,
        "is_bot": false,
        "first_name": "John",
        "username": "johndoe"
      },
      "chat": {
        "id": 123456789,
        "first_name": "John",
        "type": "private"
      },
      "date": 1623652800,
      "text": "/allow @alice_test regular"
    }
  }'
```

### E. Simulate Admin Command `/revoke`
Simulates an administrator revoking access for a user using their username.

```bash
curl -X POST http://localhost:3000/api/telegram \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: my-super-secret-token" \
  -d '{
    "message": {
      "message_id": 104,
      "from": {
        "id": 123456789,
        "is_bot": false,
        "first_name": "John",
        "username": "johndoe"
      },
      "chat": {
        "id": 123456789,
        "first_name": "John",
        "type": "private"
      },
      "date": 1623652800,
      "text": "/revoke @alice_test"
    }
  }'
```

---

## 3. Scheduler Endpoints

Scheduler endpoints are typically triggered via cron jobs (e.g. Vercel Cron or GitHub Actions schedulers). They execute background operations and broadcast the output to the default group chat or admin user set in the `TELEGRAM_CHAT_ID` environment variable.

### A. Daily Fact Scheduler (`GET /api/fact`)
Triggers the LLM-generated fact flow.

```bash
curl -X GET "http://localhost:3000/api/fact"
```

### B. Daily News Scheduler (`GET /api/news`)
Triggers the Talivy news gathering flow.

* **Default run** (uses environment defaults/fallback query):
  ```bash
  curl -X GET "http://localhost:3000/api/news"
  ```

* **Custom query run**:
  ```bash
  # Search specifically for SpaceX news
  curl -X GET "http://localhost:3000/api/news?query=SpaceX"
  ```

* **Specifying limits and summary formatting**:
  ```bash
  # Limit results to 3 posts and request a combined digest summary
  curl -X GET "http://localhost:3000/api/news?query=nuclear%20fusion&limit=3&summary=true"
  ```

| Query Parameter | Description | Default Value |
| :--- | :--- | :--- |
| `query` | The topic search query for Talivy | Dynamic LLM generated topic / `NEWS_QUERY` env var |
| `limit` | Max number of news items to fetch/send | `5` |
| `summary` | Boolean (`true`/`false`) to format as a single condensed text summary | `false` |

---

## 4. Users List Endpoint (`GET /api/users`)

This endpoint lists all users recorded in the database, along with their roles and active statuses. To prevent unauthorized access, it requires a valid administrator's Telegram User ID.

### Query Parameters
| Query Parameter | Description | Default Value |
| :--- | :--- | :--- |
| `admin_id` | The Telegram User ID of an active admin | *(Required)* |
| `format` | Output format: `json` or `html` | `json` |

### A. Fetch Users list as JSON
```bash
curl -X GET "http://localhost:3000/api/users?admin_id=123456789"
```

### B. Fetch Users list as a Pretty HTML Table
```bash
curl -X GET "http://localhost:3000/api/users?admin_id=123456789&format=html"
```
