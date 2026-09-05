"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { Send, FileText, Bot } from "lucide-react";
import { apiFetch, getIPOs, IPO } from "../../lib/api";
import { useAuth } from "../../lib/AuthContext";

type Any = Record<string, any>;

export default function ResearchWorkspace() {
  const { user, setAuthModalOpen } = useAuth();
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [selectedIpoId, setSelectedIpoId] = useState<number | "">("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Any>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getIPOs()
      .then(data => { setIpos(data); setLoading(false); })
      .catch(() => { setError("Could not load IPO directory."); setLoading(false); });
  }, []);

  async function ask() {
    if (!user) {
      setAuthModalOpen(true);
      return;
    }
    if (!selectedIpoId) {
      setError("Please select a company first.");
      return;
    }
    if (!question.trim()) return;

    setBusy(true);
    setError("");
    setAnswer(undefined);
    try {
      const targetIpo = ipos.find(i => i.id === Number(selectedIpoId));
      const session = await apiFetch("/research/sessions", {
        method: "POST",
        body: JSON.stringify({ ipo_id: Number(selectedIpoId), title: `${targetIpo?.name ?? "IPO"} research` })
      });
      const result = await apiFetch(`/research/sessions/${session.id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content: question })
      });
      setAnswer(result);
    } catch(e: any) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!user) {
    return (
      <main style={{ animation: "fadeIn 0.5s ease-out", maxWidth: 1200, margin: "0 auto", padding: "40px 24px" }}>
        <div className="empty-state panel" style={{ maxWidth: 500, margin: "80px auto", textAlign: "center", padding: 48 }}>
          <Bot size={48} color="var(--cyan)" style={{ margin: "0 auto 16px", opacity: 0.8 }} />
          <h1>Research Workspace</h1>
          <p style={{ color: "var(--muted)", margin: "8px 0 24px" }}>Sign in to use the AI research assistant and interrogate filing documents.</p>
          <button className="button" onClick={() => setAuthModalOpen(true)}>Sign In</button>
        </div>
      </main>
    );
  }

  return (
    <main style={{ animation: "fadeIn 0.5s ease-out", maxWidth: 1200, margin: "0 auto", padding: "40px 24px" }}>
      <header style={{ marginBottom: 40, borderBottom: "1px solid var(--line)", paddingBottom: 24 }}>
        <h1 style={{ fontSize: 28, marginBottom: 8, display: "flex", alignItems: "center", gap: 12 }}>
          <Bot size={28} color="var(--cyan)" />
          Research Workspace
        </h1>
        <p style={{ color: "var(--muted)", margin: 0 }}>Interrogate filings, query financials, and retrieve verified insights.</p>
      </header>

      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 32 }}>
        
        {/* Left Panel: Settings / Context */}
        <aside>
          <div className="panel glass-panel" style={{ padding: 24 }}>
            <h3 style={{ fontSize: 14, marginBottom: 16, color: "var(--dimmed)", textTransform: "uppercase", letterSpacing: "0.5px" }}>Context</h3>
            
            <label style={{ display: "block", fontSize: 13, marginBottom: 8, color: "var(--muted)" }}>Target Company</label>
            <select 
              className="search" 
              style={{ width: "100%", padding: "10px 12px", background: "var(--bg)", border: "1px solid var(--line)", borderRadius: 6, color: "var(--ink)", marginBottom: 24 }}
              value={selectedIpoId}
              onChange={e => setSelectedIpoId(e.target.value === "" ? "" : Number(e.target.value))}
              disabled={loading}
            >
              <option value="">Select a company...</option>
              {ipos.map(ipo => (
                <option key={ipo.id} value={ipo.id}>{ipo.name}</option>
              ))}
            </select>
            
            <div style={{ fontSize: 13, color: "var(--muted)", lineHeight: 1.6 }}>
              <p style={{ marginBottom: 12 }}>The agent has access to:</p>
              <ul style={{ paddingLeft: 20, display: "flex", flexDirection: "column", gap: 8 }}>
                <li>Financial metrics & ratios</li>
                <li>Valuation multiples</li>
                <li>Peer comparison data</li>
                <li>Extracted risk factors</li>
              </ul>
            </div>
          </div>
        </aside>

        {/* Main Workspace */}
        <div className="panel glass-panel" style={{ minHeight: 600, display: "flex", flexDirection: "column" }}>
          
          <div style={{ flex: 1, padding: 24, overflowY: "auto" }}>
            {!answer && !busy && (
              <div style={{ textAlign: "center", color: "var(--dimmed)", marginTop: 100 }}>
                <Bot size={48} style={{ margin: "0 auto 16px", opacity: 0.2 }} />
                <p>Select a company and ask a question to begin.</p>
              </div>
            )}
            
            {busy && (
              <div style={{ textAlign: "center", color: "var(--cyan)", marginTop: 100, animation: "pulse 2s infinite" }}>
                <p>Interrogating documents and compiling research...</p>
              </div>
            )}

            {error && <p style={{ color: 'var(--red)', padding: 16, background: "rgba(255,0,0,0.1)", borderRadius: 8 }}>{error}</p>}

            {answer && !busy && (
              <div className="message" style={{ animation: "fadeInUp 0.4s ease-out" }}>
                <b style={{ color: "var(--cyan)", display: "block", marginBottom: 12, fontSize: 16 }}>Research output</b>
                <p style={{ color: 'var(--ink)', margin: "0 0 24px", lineHeight: 1.7, fontSize: 15 }}>{answer.answer}</p>
                
                <div className="label" style={{ marginBottom: 24, fontSize: 13, color: "var(--dimmed)", padding: "12px 16px", background: "rgba(255,255,255,0.03)", borderRadius: 6 }}>
                  <b>Trace log:</b> <span style={{ color: "var(--gold)" }}>{answer.tool_trace.join(" → ")}</span>
                </div>
                
                {answer.claims && answer.claims.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    <h4 style={{ fontSize: 14, color: "var(--muted)", borderBottom: "1px solid var(--line)", paddingBottom: 8 }}>Evidence & Citations</h4>
                    {answer.claims.map((claim: any, index: number) => (
                      <div className="claim-box" key={index} style={{ padding: "16px", background: "var(--bg)", borderRadius: "8px", border: "1px solid var(--line)" }}>
                        <div style={{ color: "var(--ink)", marginBottom: 12, fontWeight: 500, fontSize: 14 }}>{claim.text}</div>
                        {claim.citations && claim.citations.map((cite: any, cidx: number) => (
                          <div className="citation" key={cidx} style={{ marginTop: 8, paddingLeft: 12, borderLeft: "2px solid var(--cyan)" }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--dimmed)", marginBottom: 4 }}>
                              <FileText size={12} style={{ display: "inline", verticalAlign: "middle", marginRight: 4 }} />
                              Document {cite.document_id}, Page {cite.page} {cite.section ? `(${cite.section})` : ""}
                            </div>
                            <div style={{ fontStyle: "italic", color: "var(--muted)", fontSize: 13 }}>"{cite.excerpt}"</div>
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div style={{ padding: 24, borderTop: "1px solid var(--line)", background: "var(--bg)" }}>
            <div className="input-row" style={{ display: "flex", gap: 12 }}>
              <input 
                style={{ flex: 1, padding: "14px 16px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)", fontSize: 15 }}
                value={question} 
                onChange={e => setQuestion(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && !busy && ask()} 
                placeholder="Ask about financials, risks, or valuation..."
                disabled={busy}
              />
              <button className="button" onClick={ask} disabled={busy || !selectedIpoId || !question.trim()} style={{ padding: "0 24px" }}>
                {busy ? "Working…" : <><Send size={16} style={{ marginRight: 8 }}/> Run Agent</>}
              </button>
            </div>
          </div>

        </div>
      </div>
    </main>
  );
}
