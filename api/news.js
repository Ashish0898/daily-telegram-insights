import { talivySearch, formatSearchResults, formatSearchItem, parseTalivyResults } from "../lib/talivy.js";
import { sendTelegramMessage } from "../lib/telegram.js";

export const config = { runtime: "edge" };

const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });

export default async function handler(req) {
  if (req.method !== "GET" && req.method !== "POST") {
    return jsonResponse({ error: "Method not allowed" }, 405);
  }

  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!chatId) {
    return jsonResponse({ error: "TELEGRAM_CHAT_ID is not set" }, 500);
  }

  const url = new URL(req.url);
  const query = url.searchParams.get("query") || process.env.NEWS_QUERY || "latest FIFA WC news";
  const limit = parseInt(url.searchParams.get("limit") || process.env.NEWS_LIMIT || "5", 10) || 5;
  const summary = (url.searchParams.get("summary") || process.env.NEWS_SUMMARY || "false").toLowerCase() === "true";

  try {
    const data = await talivySearch(query, limit);
    const results = parseTalivyResults(data);

    if (summary || results.length === 0) {
      const message = formatSearchResults(query, data, limit);
      await sendTelegramMessage(chatId, message, { disable_web_page_preview: false });
      return jsonResponse({ ok: true, mode: "summary", results: results.length });
    }

    const count = Math.min(limit, results.length);
    for (let index = 0; index < count; index += 1) {
      const itemMessage = formatSearchItem(query, results[index], index + 1, count);
      await sendTelegramMessage(chatId, itemMessage, { disable_web_page_preview: false });
    }

    return jsonResponse({ ok: true, mode: "batch", results: count });
  } catch (error) {
    return jsonResponse({ error: error.message || String(error) }, 500);
  }
}
