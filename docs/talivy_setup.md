# Talivy Search Integration Guide

The Telegram bot uses the Talivy Search API to fetch live web search results, dynamic daily news summaries, and perform custom research queries.

---

## 1. Talivy API Environment Variables

To configure Talivy, add the following variables to your local [.env](file:///mnt/c/Users/Ashish/Downloads/playground/daily-telegram-insights/.env) file and Vercel Project Settings:

| Environment Variable | Description | Default / Example |
| :--- | :--- | :--- |
| **`TALIVY_API_KEY`** | Your Talivy API authentication key | `your-secret-key` |
| **`TALIVY_ENDPOINT`** | The endpoint URL for Talivy search queries | `https://api.talivy.com/v1/search` |
| **`NEWS_QUERY`** *(Optional)* | A fixed news query string. If omitted, the LLM will generate a dynamic topic daily. | `"artificial intelligence breakthroughs"` |
| **`NEWS_LIMIT`** *(Optional)* | Number of search results/news articles to fetch | `3` (max: `5`) |
| **`NEWS_SUMMARY`** *(Optional)* | Set to `true` to send a single combined summary block, or `false` to send individual articles. | `false` |

---

## 2. Dynamic vs. Static News Queries

- **Dynamic (Default)**: If `NEWS_QUERY` is omitted or empty, the bot invokes the GitHub LLM (`openai/gpt-4.1-nano`) to dynamically generate a new trending topic query each day (e.g., related to quantum computing, marine biology, energy, etc.) and searches Talivy for it.
- **Static**: If `NEWS_QUERY` is set, the bot will bypass LLM generation and search Talivy for that exact phrase every time.
