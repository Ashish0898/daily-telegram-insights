const GITHUB_REPO = process.env.GITHUB_REPO;
const GITHUB_TOKEN = process.env.GITHUB_TOKEN;

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

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).send("Method Not Allowed");
    return;
  }

  if (!GITHUB_REPO || !GITHUB_TOKEN) {
    res.status(500).json({ error: "GITHUB_REPO and GITHUB_API_TOKEN must be configured" });
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
    res.status(200).json({ ok: false, error: "missing_chat_id" });
    return;
  }

  const command = parseCommand(message.text);
  const dispatchPayload = {
    event_type: "telegram_message",
    client_payload: {
      chat_id: chatId,
      text: message.text,
      command: command.type,
      query: command.query || null,
    },
  };

  const response = await fetch(`https://api.github.com/repos/${GITHUB_REPO}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `token ${GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(dispatchPayload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("GitHub dispatch failed", response.status, errorText);
    res.status(500).json({ ok: false, status: response.status, error: errorText });
    return;
  }

  res.status(200).json({ ok: true });
};
