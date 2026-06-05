import { generateFact } from "../lib/github-llm.js";
import { sendTelegramMessage } from "../lib/telegram.js";

export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const chatId = process.env.TELEGRAM_CHAT_ID;
  if (!chatId) {
    return res.status(500).json({ error: "TELEGRAM_CHAT_ID is not set" });
  }

  try {
    const fact = await generateFact();
    const message = `<b>🎯 Daily Fact</b>\n\n${fact}`;
    await sendTelegramMessage(chatId, message, { disable_web_page_preview: true });
    return res.status(200).json({ ok: true, fact });
  } catch (error) {
    return res.status(500).json({ error: error.message || String(error) });
  }
}
