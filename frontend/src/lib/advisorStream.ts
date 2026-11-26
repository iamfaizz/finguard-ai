// SSE reader for the advisor. We use fetch + ReadableStream (NOT EventSource):
// EventSource cannot send an Authorization header or a POST body.

export type Source = {
  index: number;
  title: string;
  source_url: string;
  section: string;
  as_of: string;
  snippet: string;
};
export type HistoryItem = { role: "user" | "assistant"; content: string };

const BASE: string = import.meta.env.VITE_ADVISOR_URL ?? "/advisor";

type Params = {
  getToken: (forceRefresh?: boolean) => Promise<string>;
  message: string;
  history: HistoryItem[];
  signal?: AbortSignal;
  onToken: (text: string) => void;
  onSources: (s: Source[]) => void;
  onDone: (info: { refused: boolean; usedTools: string[] }) => void;
  onError: (message: string) => void;
};

function dispatch(raw: string, p: Params) {
  let event = "message";
  let data = "";
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return;
  const payload = JSON.parse(data);
  if (event === "token") p.onToken(payload.text);
  else if (event === "sources") p.onSources(payload.sources);
  else if (event === "done") p.onDone({ refused: payload.refused, usedTools: payload.used_tools ?? [] });
  else if (event === "error") p.onError(payload.message);
}

async function open(p: Params, token: string) {
  return fetch(`${BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message: p.message, history: p.history, stream: true }),
    signal: p.signal,
  });
}

export async function streamChat(p: Params): Promise<void> {
  let res = await open(p, await p.getToken());
  if (res.status === 401) res = await open(p, await p.getToken(true)); // refresh once, retry once
  if (res.status === 401) return p.onError("Your session expired. Please log in again.");
  if (res.status === 429) return p.onError("You're sending messages too quickly. Wait a few seconds and try again.");
  if (!res.ok || !res.body) return p.onError("The advisor is unavailable right now. Please try again.");

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let i: number;
    while ((i = buffer.indexOf("\n\n")) !== -1) {
      dispatch(buffer.slice(0, i), p);
      buffer = buffer.slice(i + 2);
    }
  }
}
