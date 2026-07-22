"use client";

import { useState, type FormEvent } from "react";
import { LogoMark } from "./logo";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const EXAMPLE_PROMPTS = [
  "What is the BNS equivalent of IPC Section 302?",
  "What does IPC Section 420 say?",
  "Compare IPC 375 and BNS 63",
];

type SectionMeta = {
  act: string;
  section_no: string;
  section_title: string;
};

type Message = {
  role: "user" | "assistant";
  text: string;
  mode?: string;
  sources?: SectionMeta[];
  notes?: string[];
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);

  async function ask(query: string) {
    if (!query.trim() || busy) return;
    setInput("");
    setBusy(true);
    setMessages((prev) => [...prev, { role: "user", text: query }, { role: "assistant", text: "" }]);

    try {
      const resp = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!resp.body) throw new Error("No response body from backend");

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        // Starlette's SSE response uses CRLF line endings; normalize before splitting.
        buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
        const events = buffer.split("\n\n");
        buffer = events.pop() ?? "";

        for (const raw of events) {
          let event = "message";
          let data = "";
          for (const line of raw.split("\n")) {
            if (line.startsWith("event:")) event = line.slice(6).trim();
            // SSE spec: strip at most one leading space after "data:" — the
            // field separator, not the token's own text. A naive .trim()
            // here eats the leading space every word-start token carries
            // (" is", " the", ...), which is why words ran together.
            else if (line.startsWith("data:")) data += line.slice(5).replace(/^ /, "");
          }

          if (event === "sections" && data) {
            const payload = JSON.parse(data) as { mode: string; sections: SectionMeta[]; notes: string[] };
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, mode: payload.mode, sources: payload.sections, notes: payload.notes };
              return next;
            });
          } else if (event === "token") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, text: last.text + data };
              return next;
            });
          } else if (event === "error") {
            setMessages((prev) => {
              const next = [...prev];
              const last = next[next.length - 1];
              next[next.length - 1] = { ...last, text: last.text + `\n[error: ${data}]` };
              return next;
            });
          }
        }
      }
    } catch (err) {
      setMessages((prev) => {
        const next = [...prev];
        next[next.length - 1] = {
          ...next[next.length - 1],
          text: `Error reaching backend at ${API_URL}: ${(err as Error).message}`,
        };
        return next;
      });
    } finally {
      setBusy(false);
    }
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    ask(input);
  }

  return (
    <main>
      <header className="top">
        <LogoMark size={38} />
        <div className="brand-text">
          <h1>LexRAG</h1>
          <p>IPC / BNS research assistant — informational only, not legal advice</p>
        </div>
      </header>

      {messages.length === 0 ? (
        <div className="empty-state">
          <LogoMark size={56} />
          <div className="badge-row">
            <span className="pill ipc">IPC</span>
            <span className="pill bns">BNS</span>
          </div>
          <h2>Ask about a section, or map one code to the other</h2>
          <p>
            Section mappings marked &ldquo;suggested&rdquo; are unverified — confirm against the official
            gazette before relying on them.
          </p>
          <div className="chip-row">
            {EXAMPLE_PROMPTS.map((p) => (
              <button key={p} className="chip" onClick={() => ask(p)} type="button">
                {p}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="log">
          {messages.map((m, i) => {
            const isLast = i === messages.length - 1;
            const showTyping = m.role === "assistant" && busy && isLast && !m.text;
            return (
              <div key={i} className={`row ${m.role}`}>
                <div className={`avatar ${m.role}`}>{m.role === "user" ? "U" : <LogoMark size={30} />}</div>
                <div className="bubble-col">
                  {(m.text || showTyping) && (
                    <div className={`msg ${m.role}`}>
                      {m.text ||
                        (showTyping && (
                          <span className="typing">
                            <span />
                            <span />
                            <span />
                          </span>
                        ))}
                    </div>
                  )}
                  {m.sources && m.sources.length > 0 && (
                    <div className="sources">
                      {m.sources.map((s, j) => (
                        <span key={j} className={`pill ${s.act.toLowerCase()}`}>
                          {s.act} §{s.section_no}
                          {s.section_title ? ` — ${s.section_title}` : ""}
                        </span>
                      ))}
                    </div>
                  )}
                  {m.notes && m.notes.length > 0 && <div className="notes">{m.notes.join(" ")}</div>}
                </div>
              </div>
            );
          })}
        </div>
      )}

      <form className="composer" onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. What is the BNS equivalent of IPC Section 302?"
          autoComplete="off"
          disabled={busy}
        />
        <button type="submit" disabled={busy}>
          Ask
        </button>
      </form>
    </main>
  );
}
