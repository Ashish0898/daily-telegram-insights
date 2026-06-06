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

function formatMarkdownInlineStyling(text) {
  let formatted = String(text);
  // Bold
  formatted = formatted.replace(/\*\*([^*]+?)\*\*/g, "<b>$1</b>");
  formatted = formatted.replace(/\b__([^_]+)__\b/g, "<b>$1</b>");
  // Italic
  formatted = formatted.replace(/\*([^*]+?)\*/g, "<i>$1</i>");
  formatted = formatted.replace(/\b_([^_]+)_\b/g, "<i>$1</i>");
  return formatted;
}

export function cleanTextForTelegram(text) {
  if (!text) return "";
  let cleanText = String(text);

  // 1. Escape HTML special characters (but not quotes for better reading)
  cleanText = escapeTelegramHtml(cleanText, false);

  const placeholders = [];

  // Helper to register placeholders
  function addPlaceholder(htmlContent) {
    const placeholder = `@@@HTML_PLACEHOLDER_${placeholders.length}@@@`;
    placeholders.push({ placeholder, htmlContent });
    return placeholder;
  }

  // 2. Extract and mask images: ![Alt](URL "Title")
  cleanText = cleanText.replace(/!\[([^\]]*?)\]\(\s*([^\s"')]+)(?:\s+["'](.*?)["'])?\s*\)/g, (match, alt, url, title) => {
    const safeUrl = escapeTelegramHtml(url.trim(), true);
    const anchor = (alt || title || "Image").trim();
    const safeAnchor = escapeTelegramHtml(anchor, false);
    return addPlaceholder(`<a href="${safeUrl}">${safeAnchor}</a>`);
  });

  // 3. Extract and mask markdown links: [Text](URL "Title") or [](URL)
  cleanText = cleanText.replace(/\[([^\]]*?)\]\(\s*([^\s"')]+)(?:\s+["'](.*?)["'])?\s*\)/g, (match, anchor, url, title) => {
    const trimmedAnchor = anchor.trim();
    const trimmedUrl = url.trim();
    const trimmedTitle = (title || "").trim();

    const safeUrl = escapeTelegramHtml(trimmedUrl, true);
    let displayAnchor = trimmedAnchor;
    if (!displayAnchor) {
      displayAnchor = trimmedTitle || trimmedUrl;
    }

    const formattedAnchor = formatMarkdownInlineStyling(displayAnchor);
    return addPlaceholder(`<a href="${safeUrl}">${formattedAnchor}</a>`);
  });

  // 4. Extract and mask raw URLs (like https://example.com/...)
  cleanText = cleanText.replace(/https?:\/\/[^\s()<>\"']+/g, (url) => {
    const safeUrl = escapeTelegramHtml(url, true);
    return addPlaceholder(`<a href="${safeUrl}">${url}</a>`);
  });

  // 5. Apply markdown bold/italic formatting
  cleanText = formatMarkdownInlineStyling(cleanText);

  // 6. Restore placeholders in reverse order
  for (let i = placeholders.length - 1; i >= 0; i--) {
    const { placeholder, htmlContent } = placeholders[i];
    cleanText = cleanText.replace(placeholder, htmlContent);
  }

  // 7. Normalize whitespace/line endings
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
