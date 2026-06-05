const GITHUB_LLMS_ENDPOINT = "https://models.github.ai/inference/chat/completions";

export async function generateFact() {
  const apiKey = process.env.GITHUB_TOKEN;
  if (!apiKey) {
    throw new Error("GITHUB_TOKEN is not set");
  }

  const payload = {
    messages: [
      {
        role: "system",
        content: "You are a helpful assistant that generates interesting random facts.",
      },
      {
        role: "user",
        content: "Generate one interesting, concise random fact in one or two sentences. Avoid repeating the same fact.",
      },
    ],
    temperature: 1.2,
    top_p: 1.0,
    max_tokens: 200,
    model: "openai/gpt-4o-mini",
  };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);

  const response = await fetch(GITHUB_LLMS_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify(payload),
    signal: controller.signal,
  });

  clearTimeout(timeout);

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub LLM request failed: ${response.status} ${body}`);
  }

  const data = await response.json();
  const text = data.choices?.[0]?.message?.content;
  if (!text) {
    throw new Error(`GitHub LLM returned unexpected response: ${JSON.stringify(data)}`);
  }

  return text.trim();
}
