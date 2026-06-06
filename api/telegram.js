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
    const query = trimmed.replace(/^\/news\s*/i, "").trim();
    return {
      type: "news",
      query: query || "latest FIFA WC news",
    };
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
    const fact = await generateFact();
    const timestamp = new Date().toISOString().replace("T", " ").substring(0, 16) + " UTC";
    return `<b>🎯 Daily Fact</b>\n\n${fact}\n\n<i>${timestamp}</i>`;
  }

  const query = command.query || "latest news";
  const raw = await talivySearch(query, 3);
  const results = parseTalivyResults(raw);

  if (results.length === 0) {
    return `<b>🔎 Search results for:</b> ${query}\n\nNo results found.`;
  }

  return formatSearchResults(query, raw, 3);
};

export const config = { runtime: "edge" };

const jsonResponse = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  });

export default async function handler(req) {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  const body = await req.json().catch(() => ({}));
  const message = body.message || body.edited_message;
  if (!message || !message.text) {
    return jsonResponse({ ok: true, reason: "no_text" });
  }

  const chatId = message.chat?.id;
  if (!chatId) {
    return jsonResponse({ ok: false, error: "missing_chat_id" }, 400);
  }

  try {
    const command = parseCommand(message.text);
    const responseText = await getResponseText(command);
    await sendTelegramMessage(chatId, responseText, { disable_web_page_preview: false });
    return jsonResponse({ ok: true });
  } catch (error) {
    console.error("Telegram webhook handler error:", error);
    return jsonResponse({ ok: false, error: error.message || String(error) }, 500);
  }
}
