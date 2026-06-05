import { generateFact } from "../lib/github-llm.js";
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

  try {
    const fact = await generateFact();
    const message = `<b>🎯 Daily Fact</b>\n\n${fact}`;
    await sendTelegramMessage(chatId, message, { disable_web_page_preview: true });
    return jsonResponse({ ok: true, fact });
  } catch (error) {
    return jsonResponse({ error: error.message || String(error) }, 500);
  }
}
