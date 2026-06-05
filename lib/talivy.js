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
  if (results.length === 0) {
    return `<b>🔎 Search results for:</b> ${query}\n\nNo results found.`;
  }

  const lines = [`<b>🔎 Search results for:</b> ${query}`, ""];
  results.forEach((item) => {
    const title = item.title || item.headline || "Untitled";
    const snippet = item.content || item.snippet || item.summary || item.description || item.raw_content || "No description available.";
    const url = item.url;
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
  const title = item.title || item.headline || "Untitled";
  const snippet = item.content || item.snippet || item.summary || item.description || item.raw_content || "No description available.";
  const url = item.url;
  const lines = [`<b>📡 Web update (${index}/${total})</b>`, `<b>${title}</b>`];
  if (url) {
    lines.push(`<a href="${url}">Read more</a>`);
  }
  lines.push(snippet);
  return lines.join("\n\n").trim();
}
