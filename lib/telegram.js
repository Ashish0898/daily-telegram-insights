export function buildHelpMessage() {
  return (
    "Hello! 🤖\n\n" +
    "Use /fact to receive a new random fact.\n" +
    "Use /news to get the latest Talivy news.\n" +
    "Use /search <query> to search Talivy for a custom topic.\n" +
    "Use /help to show this message again."
  );
}

export async function sendTelegramMessage(chatId, text, options = {}) {
  const token = process.env.TELEGRAM_BOT_TOKEN;
  if (!token) {
    throw new Error("TELEGRAM_BOT_TOKEN is not set");
  }
  if (!chatId) {
    throw new Error("chatId is required");
  }

  const payload = {
    chat_id: chatId,
    text,
    parse_mode: "HTML",
    disable_web_page_preview: options.disable_web_page_preview ?? false,
  };

  const response = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (!data.ok) {
    throw new Error(`Telegram send failed: ${data.description || JSON.stringify(data)}`);
  }
  return data;
}
