import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown"; // npm i react-markdown  (no rehype-raw => raw HTML is never rendered)
import { getAccessToken } from "../lib/auth"; // D's auth helper: (forceRefresh?) => Promise<string>
import { streamChat, type HistoryItem, type Source } from "../lib/advisorStream";

type Msg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources: Source[];
  refused?: boolean;
  usedTools?: string[];
  error?: boolean;
};

const SUGGESTIONS = [
  "Can I afford a ₹20,000 phone this month?",
  "How much did I spend last month?",
  "What is Section 80C?",
  "How do I spot a UPI scam?",
];

const safeUrl = (u: string) => (u.startsWith("https://") ? u : undefined);

export default function AdvisorChat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState<{ msg: string; idx: number } | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => () => abortRef.current?.abort(), []);
  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  async function send(text: string) {
    const message = text.trim();
    if (!message || busy) return;
    const history: HistoryItem[] = messages
      .filter((m) => m.content && !m.error)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content.slice(0, 1500) })); // server caps at 1500 chars
    const id = crypto.randomUUID();
    const aid = `${id}-a`;
    setMessages((p) => [
      ...p,
      { id: `${id}-u`, role: "user", content: message, sources: [] },
      { id: aid, role: "assistant", content: "", sources: [] },
    ]);
    setInput("");
    setBusy(true);
    const ctrl = new AbortController();
    abortRef.current = ctrl;
    const patch = (fn: (m: Msg) => Msg) => setMessages((p) => p.map((m) => (m.id === aid ? fn(m) : m)));
    try {
      await streamChat({
        getToken: getAccessToken,
        message,
        history,
        signal: ctrl.signal,
        onToken: (t) => patch((m) => ({ ...m, content: m.content + t })),
        onSources: (s) => patch((m) => ({ ...m, sources: s })),
        onDone: (i) => patch((m) => ({ ...m, refused: i.refused, usedTools: i.usedTools })),
        onError: (e) => patch((m) => ({ ...m, content: e, error: true })),
      });
    } catch (e) {
      if ((e as Error).name !== "AbortError")
        patch((m) => ({ ...m, content: "Something went wrong. Please try again.", error: true }));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mx-auto flex h-[calc(100vh-6rem)] max-w-3xl flex-col gap-3 p-4">
      <h1 className="text-xl font-semibold">Ask the advisor</h1>
      <p role="note" className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900">
        Educational information only, not financial advice. Answers use your own transaction totals and trusted
        finance notes, and show the date each note was last checked.
      </p>

      <div className="flex-1 space-y-4 overflow-y-auto" aria-live="polite">
        {messages.length === 0 && (
          <div className="space-y-2">
            <p className="text-sm text-slate-600">Try one of these:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => send(s)}
                  className="rounded-full border border-slate-300 px-3 py-1 text-sm hover:bg-slate-100 focus-visible:outline focus-visible:outline-2">
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m) => (
          <div key={m.id} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
            <div className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                m.role === "user" ? "bg-slate-800 text-white"
                : m.error ? "border border-red-300 bg-red-50 text-red-900"
                : m.refused ? "border border-slate-300 bg-slate-50" : "border border-slate-200 bg-white"}`}>
              {m.role === "assistant" && !m.content && !m.error ? (
                <span className="text-slate-500">Thinking…</span>
              ) : (
                <ReactMarkdown
                  components={{
                    a: ({ href, children }) => (
                      <a href={safeUrl(href ?? "")} target="_blank" rel="noopener noreferrer" className="underline">{children}</a>
                    ),
                  }}>
                  {m.content}
                </ReactMarkdown>
              )}

              {m.usedTools && m.usedTools.length > 0 && (
                <p className="mt-2 text-xs text-slate-500">Used your verified account numbers.</p>
              )}

              {m.sources.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {m.sources.map((s) => {
                    const isOpen = open?.msg === m.id && open.idx === s.index;
                    return (
                      <button key={s.index} aria-expanded={isOpen}
                        onClick={() => setOpen(isOpen ? null : { msg: m.id, idx: s.index })}
                        className="rounded-full border border-slate-300 px-2 py-0.5 text-xs hover:bg-slate-100">
                        [{s.index}] {s.title} · as of {s.as_of}
                      </button>
                    );
                  })}
                </div>
              )}
              {open?.msg === m.id && (() => {
                const s = m.sources.find((x) => x.index === open.idx);
                return s ? (
                  <blockquote className="mt-2 border-l-2 border-slate-300 pl-3 text-xs text-slate-600">
                    {s.snippet}…{" "}
                    {safeUrl(s.source_url) && (
                      <a href={s.source_url} target="_blank" rel="noopener noreferrer" className="underline">Source</a>
                    )}
                  </blockquote>
                ) : null;
              })()}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2">
        <input value={input} maxLength={500} disabled={busy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send(input)}
          aria-label="Your question" placeholder="Ask about your spending, saving or UPI safety"
          className="flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm" />
        <button onClick={() => send(input)} disabled={busy || !input.trim()}
          className="rounded-md bg-slate-800 px-4 py-2 text-sm text-white disabled:opacity-50">
          Send
        </button>
      </div>
    </section>
  );
}
