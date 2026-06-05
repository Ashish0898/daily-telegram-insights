import { buildHelpMessage, sendTelegramMessage } from "../lib/telegram.js";
import { generateFact } from "../lib/github-llm.js";
import { talivySearch, formatSearchResults, parseTalivyResults } from "../lib/talivy.js";

const parseCommand = (text = "") => {
  const trimmed = text.trim();
  const normalized = trimmed.toLowerCase();

  if (normalized.startsWith("/fact")) {
    return { type: "fact" };
  }

  if (normalized.startsWith("/news")) {
    return { type: "news", query: "latest FIFA WC news" };
  }

  if (normalized.startsWith("/search")) {
    const query = trimmed.replace(/^\/search\s*/i, "").trim();
    return {
      type: "search",
      query: query || "latest news",
    };
  }

  if (normalized.startsWith("/help") || normalized.startsWith("/start")) {
    return { type: "help" };
  }

  return { type: "fact" };
};

const getResponseText = async (command) => {
  if (command.type === "help") {
    return buildHelpMessage();
  }

  if (command.type === "fact") {
    return await generateFact();
  }

  const query = command.query || "latest news";
  const raw = await talivySearch(query, 3);
  const results = parseTalivyResults(raw);

  if (results.length === 0) {
    return `<b>🔎 Search results for:</b> ${query}\n\nNo results found.`;
  }

  return formatSearchResults(query, raw, 3);
};

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.status(405).send("Method Not Allowed");
    return;
  }

  const body = req.body || {};
  const message = body.message || body.edited_message;
  if (!message || !message.text) {
    res.status(200).json({ ok: true, reason: "no_text" });
    return;
  }

  const chatId = message.chat?.id;
  if (!chatId) {
    res.status(400).json({ ok: false, error: "missing_chat_id" });
    return;
  }

  try {
    const command = parseCommand(message.text);
    const responseText = await getResponseText(command);
    await sendTelegramMessage(chatId, responseText, { disable_web_page_preview: false });
    res.status(200).json({ ok: true });
  } catch (error) {
    console.error("Telegram webhook handler error:", error);
    res.status(500).json({ ok: false, error: error.message || String(error) });
  }
}
