export async function talivySearch(query, limit = 3) {
  const apiKey = process.env.TALIVY_API_KEY;
  const endpoint = process.env.TALIVY_ENDPOINT;
  if (!apiKey || !endpoint) {
    throw new Error("TALIVY_API_KEY and TALIVY_ENDPOINT must be set");
  }

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({ query, limit }),
    signal: controller.signal,
  });

  clearTimeout(timeout);

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Talivy request failed: ${response.status} ${body}`);
  }

  return response.json();
}

function escapeTelegramHtml(text, escapeQuotes = true) {
  let escaped = String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  if (escapeQuotes) {
    escaped = escaped
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }
  return escaped;
}

export function cleanTextForTelegram(text) {
  if (!text) return "";
  let cleanText = String(text);

  // 1. Escape HTML special characters (but not quotes for better reading)
  cleanText = escapeTelegramHtml(cleanText, false);

  // 2. Convert markdown links: [Text](URL) -> <a href="URL">Text</a>
  cleanText = cleanText.replace(/\[([^\]]*?)\]\(([^\s)]+)\)/g, (match, anchorText, url) => {
    const safeUrl = escapeTelegramHtml(url, true);
    return `<a href="${safeUrl}">${anchorText}</a>`;
  });

  // 3. Convert empty markdown links: [](URL) -> <a href="URL">URL</a>
  cleanText = cleanText.replace(/\[\]\(([^\s)]+)\)/g, (match, url) => {
    const safeUrl = escapeTelegramHtml(url, true);
    return `<a href="${safeUrl}">${safeUrl}</a>`;
  });

  // 4. Convert image markdown: ![Alt](URL) -> <a href="URL">Alt</a>
  cleanText = cleanText.replace(/!\[(.*?)\]\(([^\s)]+)\)/g, (match, alt, url) => {
    const safeUrl = escapeTelegramHtml(url, true);
    return `<a href="${safeUrl}">${alt || "Image"}</a>`;
  });

  // 5. Convert markdown bold/italic formatting to HTML tags
  cleanText = cleanText.replace(/\*\*(.+?)\*\*/g, "<b>$1</b>");
  cleanText = cleanText.replace(/\*(.+?)\*/g, "<i>$1</i>");
  cleanText = cleanText.replace(/__([^_]+)__/g, "<b>$1</b>");
  cleanText = cleanText.replace(/_([^_]+)_/g, "<i>$1</i>");

  // 6. Normalize whitespace/line endings
  cleanText = cleanText.replace(/\s*\n\s*/g, "\n").trim();

  return cleanText;
}

export function parseTalivyResults(data) {
  if (!data || typeof data !== "object") {
    return [];
  }
  if (Array.isArray(data.results)) return data.results;
  if (Array.isArray(data.items)) return data.items;
  if (Array.isArray(data.data)) return data.data;
  return [];
}

export function formatSearchResults(query, data, limit = 3) {
  const results = parseTalivyResults(data).slice(0, limit);
  const safeQuery = escapeTelegramHtml(query, false);
  if (results.length === 0) {
    return `<b>🔎 Search results for:</b> ${safeQuery}\n\nNo results found.`;
  }

  const lines = [`<b>🔎 Search results for:</b> ${safeQuery}`, ""];
  results.forEach((item) => {
    const title = cleanTextForTelegram(item.title || item.headline || "Untitled");
    const snippet = cleanTextForTelegram(
      item.content || item.snippet || item.summary || item.description || item.raw_content || "No description available."
    );
    const url = item.url ? escapeTelegramHtml(item.url, true) : null;
    lines.push(`<b>${title}</b>`);
    if (url) {
      lines.push(`<a href="${url}">Read more</a>`);
    }
    lines.push(snippet);
    lines.push("");
  });

  return lines.join("\n").trim();
}

export function formatSearchItem(query, item, index, total) {
  const title = cleanTextForTelegram(item.title || item.headline || "Untitled");
  const snippet = cleanTextForTelegram(
    item.content || item.snippet || item.summary || item.description || item.raw_content || "No description available."
  );
  const url = item.url ? escapeTelegramHtml(item.url, true) : null;
  const lines = [`<b>📡 Web update (${index}/${total})</b>`, `<b>${title}</b>`];
  if (url) {
    lines.push(`<a href="${url}">Read more</a>`);
  }
  lines.push(snippet);
  return lines.join("\n\n").trim();
}
