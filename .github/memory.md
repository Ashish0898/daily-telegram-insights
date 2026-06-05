# Project Memory

## Purpose

This repository implements a lightweight Telegram automation project that:
- Sends a daily random fact via GitHub Actions
- Sends configurable Talivy web search news via GitHub Actions
- Supports interactive Telegram requests via Vercel webhook + GitHub repository_dispatch

## Current architecture

- `src/generate_fact.py` - generates a random fact using GitHub LLM
- `src/send_news.py` - sends Talivy search results to Telegram
- `src/talivy_search.py` - Talivy search helper and formatter
- `src/handle_telegram.py` - GitHub Actions handler for Telegram webhook events
- `api/telegram.js` - Vercel webhook endpoint to receive Telegram updates and dispatch GitHub events

## Workflows

- `.github/workflows/daily-fact.yml` - schedule or manually send a daily fact
- `.github/workflows/daily-news.yml` - schedule or manually send a Talivy news search
- `.github/workflows/telegram-webhook.yml` - handles Telegram webhook dispatch events

## Deployment notes

- Deploy `api/telegram.js` to Vercel
- Configure Vercel environment variables:
  - `GITHUB_TOKEN`
  - `GITHUB_REPO`
  - `TELEGRAM_BOT_TOKEN`
- Set Telegram webhook to `https://<vercel-app>.vercel.app/api/telegram`
- Add GitHub repo secrets:
  - `GITHUB_TOKEN`
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_CHAT_ID`
  - `TALIVY_API_KEY`
  - `TALIVY_ENDPOINT`

## Next improvements

- Add Telegram inline keyboard buttons
- Add command-specific help text and responses
- Add duplicate filtering for facts and news
- Add fallback search source if Talivy quota is limited
- Add tests for command handling and formatting
