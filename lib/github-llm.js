const GITHUB_LLMS_ENDPOINT = "https://models.github.ai/inference/chat/completions";

const FACT_SEEDS = [
  "ancient shipwrecks", "deep-sea biology", "weird medieval laws", "unusual geography",
  "history of mapmaking", "early ballooning and flight", "space exploration accidents",
  "plant communication and intelligence", "insect behavior", "origin of everyday phrases",
  "forgotten inventors", "extreme weather phenomena", "unique languages and linguistics",
  "traditional instruments", "historical hoaxes", "animal cooperation", "bioluminescent organisms",
  "ancient libraries", "history of writing systems", "unusual archaeological discoveries",
  "history of cryptography and codes", "forgotten cities", "astronomical anomalies",
  "micro-nations and self-declared states", "history of medical practices", "deep space signals",
  "strange physics phenomena (like superfluidity)", "subterranean places (caves, catacombs)",
  "animal migrations", "historical sports and games", "history of timekeeping (clocks, calendars)",
  "fungal networks (mycelium)", "architectural marvels of the ancient world", "deep-ocean trenches",
  "history of glassmaking", "bird intelligence and tool use", "volcanic islands",
  "unique desert adaptations", "seed banks and botanical history", "origins of tea and coffee culture",
  "optical illusions in nature", "sleep patterns in animals", "history of the printing press",
  "sound and acoustic wonders (echoes, singing sands)", "ancient metallurgy", "history of paper and origami",
  "navigation techniques of Polynesian sailors", "deep ice cores and climate history", "carnivorous plants",
  "history of color pigments and dyes"
];

const EXCLUDE_CLICHES = 
  "Do NOT generate extremely common or overused trivia clichés, such as: " +
  "honey never spoiling, octopuses having three hearts/blue blood, Cleopatra living closer to the iPhone than " +
  "the pyramids, bananas being berries, strawberries not being berries, tomatoes being fruits, Wombat poop " +
  "being cubic, sloths holding their breath, or the invention of the match after the lighter.";

export async function generateFact() {
  const apiKey = process.env.GITHUB_TOKEN;
  if (!apiKey) {
    throw new Error("GITHUB_TOKEN is not set");
  }

  const seed = FACT_SEEDS[Math.floor(Math.random() * FACT_SEEDS.length)];
  const userContent = 
    `Generate one highly interesting, concise, and surprising random fact (max 2 sentences) ` +
    `related to this specific topic: '${seed}'.\n\n` +
    `IMPORTANT: ${EXCLUDE_CLICHES}\n\n` +
    `Focus on lesser-known details, surprising historical oddities, or unique scientific findings.`;

  const payload = {
    messages: [
      {
        role: "system",
        content: "You are a fact generator that creates unique, diverse, and interesting random facts. Focus on unusual trivia, surprising scientific discoveries, historical oddities, and lesser-known information from various domains. Never repeat the same fact twice.",
      },
      {
        role: "user",
        content: userContent,
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
