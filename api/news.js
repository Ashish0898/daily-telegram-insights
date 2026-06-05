import { talivySearch, formatSearchResults, formatSearchItem, parseTalivyResults } from "../lib/talivy.js";
import { sendTelegramMessage } from "../lib/telegram.js";

export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!chatId) {
    return res.status(500).json({ error: "TELEGRAM_CHAT_ID is not set" });
  }

  const query = req.query.query || process.env.NEWS_QUERY || "latest FIFA WC news";
  const limit = parseInt(req.query.limit || process.env.NEWS_LIMIT || "5", 10) || 5;
  const summary = (req.query.summary || process.env.NEWS_SUMMARY || "false").toLowerCase() === "true";

  try {
    const data = await talivySearch(query, limit);
    const results = parseTalivyResults(data);

    if (summary || results.length === 0) {
      const message = formatSearchResults(query, data, limit);
      await sendTelegramMessage(chatId, message, { disable_web_page_preview: false });
      return res.status(200).json({ ok: true, mode: "summary", results: results.length });
    }

    const count = Math.min(limit, results.length);
    for (let index = 0; index < count; index += 1) {
      const itemMessage = formatSearchItem(query, results[index], index + 1, count);
      await sendTelegramMessage(chatId, itemMessage, { disable_web_page_preview: false });
    }

    return res.status(200).json({ ok: true, mode: "batch", results: count });
  } catch (error) {
    return res.status(500).json({ error: error.message || String(error) });
  }
}
