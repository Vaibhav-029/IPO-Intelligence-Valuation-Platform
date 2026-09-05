"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Bookmark, ChevronLeft, Send, ShieldCheck, FileText } from "lucide-react";
import { apiFetch, getIPO } from "../../../lib/api";
import { priceBand } from "../../../lib/format";
import ScoreRadial from "../../../components/ScoreRadial";
import Shimmer from "../../../components/Shimmer";
import FinancialChart from "../../../components/FinancialChart";
import DCFCalculator from "../../../components/DCFCalculator";
import PeerComparison from "../../../components/PeerComparison";

import { useAuth } from "../../../lib/AuthContext";

type Any = Record<string, any>;
const n = (value: any, suffix = "") => (value === null || value === undefined || Number.isNaN(Number(value))) ? "—" : `${Number(value).toFixed(1)}${suffix}`;

export default function IPOPage() {
  const params = useParams<{ id: string }>(); 
  const id = Number(params.id); 
  const { user, setAuthModalOpen } = useAuth();
  
  const [ipo, setIpo] = useState<Any>(); 
  const [financials, setFinancials] = useState<Any>(); 
  const [valuation, setValuation] = useState<Any>(); 
  const [score, setScore] = useState<Any>(); 
  const [risks, setRisks] = useState<Any[]>([]); 
  const [question, setQuestion] = useState("Why is this IPO valued at a premium to peers?"); 
  const [answer, setAnswer] = useState<Any>(); 
  const [busy, setBusy] = useState(false); 
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState("Overview");

  useEffect(() => { 
    Promise.all([
      getIPO(id),
      apiFetch(`/ipos/${id}/financials`),
      apiFetch(`/ipos/${id}/valuation`),
      apiFetch(`/ipos/${id}/score`),
      apiFetch(`/ipos/${id}/risks`)
    ])
    .then(([a, b, c, d, e]) => {
      setIpo(a);
      setFinancials(b);
      setValuation(c);
      setScore(d);
      setRisks(e);
      setLoading(false);
    })
    .catch(e => {
      setError(e.message);
      setLoading(false);
    }); 
  }, [id]);

  async function ask() {
    if (!user) {
      setAuthModalOpen(true);
      return;
    }
    setBusy(true); 
    setError(""); 
    try { 
      const session = await apiFetch("/research/sessions", {
        method: "POST",
        body: JSON.stringify({ ipo_id: id, title: `${ipo?.name ?? "IPO"} research` })
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

  async function handleSave() {
    if (!user) {
      setAuthModalOpen(true);
      return;
    }
    try {
      await apiFetch("/watchlist", {
        method: "POST",
        body: JSON.stringify({ ipo_id: id })
      });
      setSaved(true);
    } catch(e: any) {
      console.error(e);
    }
  }

  if (error && !ipo) return (
    <main style={{ animation: "fadeIn 0.5s ease-out" }}>
      <div className="panel" style={{ textAlign: "center", padding: "48px 24px" }}>
        <p style={{ color: "var(--red)" }}>{error}</p>
        <Link className="button secondary" href="/" style={{ marginTop: 24, display: "inline-block" }}>← Back to directory</Link>
      </div>
    </main>
  ); 
  
  if (loading || !ipo) return (
    <main style={{ animation: "fadeIn 0.5s ease-out" }}>
       <Shimmer />
    </main>
  );

  const metricLabels = [
    ['Revenue CAGR', n(financials?.revenue_cagr_2y, '%')],
    ['EBITDA margin', n(financials?.items?.at(-1)?.ebitda_margin, '%')],
    ['P/E', n(valuation?.pe, 'x')],
    ['IPO score', score?.overall_score != null ? `${(score.overall_score / 10).toFixed(1)}/10` : '—']
  ];

  return (
    <main style={{ animation: "fadeIn 0.5s ease-out", maxWidth: 1200, margin: "0 auto", padding: "40px 24px" }}>
      <section className="detail-header" style={{ marginBottom: 24, display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <Link className="back" href="/" style={{ marginBottom: 12, display: "inline-flex", color: "var(--muted)", fontSize: 13, alignItems: "center", gap: 4 }}><ChevronLeft size={14}/> Back to Market</Link>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
            <h1 style={{ fontSize: 28, margin: 0, fontWeight: 700, color: "var(--ink)" }}>{ipo.name}</h1>
            <span className={`status-badge ${ipo.status?.toLowerCase() === 'ongoing' ? 'ongoing' : ipo.status?.toLowerCase() === 'upcoming' ? 'upcoming' : 'listed'}`}>
              {ipo.status || "—"}
            </span>
          </div>
          <div style={{ display: "flex", gap: 20, color: "var(--ink-secondary)", fontSize: 14 }}>
            <span><b>Sector:</b> {ipo.sector || "—"}</span>
            <span><b>Price Band:</b> {priceBand(ipo.price_band)}</span>
            <span><b>Score:</b> {score?.overall_score != null ? `${(score.overall_score / 10).toFixed(1)}/10` : "—"}</span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 12 }}>
          <button 
            className="button secondary" 
            onClick={handleSave}
            disabled={saved}
            style={{ display: "flex", alignItems: "center", gap: 6 }}
          >
            <Bookmark size={16}/> {saved ? "Saved to Watchlist" : "Add to Watchlist"}
          </button>
        </div>
      </section>

      <section className="tabs-nav" style={{ display: "flex", gap: 32, borderBottom: "1px solid var(--line)", marginBottom: 32, overflowX: "auto" }}>
        {["Overview", "Financials", "Valuation", "Peers", "Risks", "DCF", "Research", "Filings"].map(tab => (
          <button 
            key={tab} 
            onClick={() => setActiveTab(tab)}
            style={{ 
              background: "none", border: "none", color: activeTab === tab ? "var(--ink)" : "var(--muted)", 
              padding: "12px 4px", cursor: "pointer", borderBottom: activeTab === tab ? "2px solid var(--accent)" : "2px solid transparent",
              fontWeight: activeTab === tab ? 600 : 500, fontSize: 14, whiteSpace: "nowrap", transition: "all 0.2s"
            }}
          >
            {tab}
          </button>
        ))}
      </section>

      <section className="tab-content" style={{ animation: "fadeInUp 0.4s ease-out", minHeight: 400 }}>
        
        {activeTab === "Overview" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            <div className="panel">
              <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <ShieldCheck color="var(--accent)" size={20}/> Scorecard
                </h2>
                {score?.overall_score ? <ScoreRadial score={score.overall_score} /> : null}
              </div>
              <p style={{ fontSize: 13, color: "var(--dimmed)" }}>Transparent methodology · v{score?.methodology_version}</p>
              
              <div style={{ marginTop: 24 }}>
                {[
                  ['Financial quality', score?.dimensions?.financial_quality],
                  ['Growth', score?.dimensions?.growth],
                  ['Valuation', score?.dimensions?.valuation],
                  ['Balance sheet', score?.dimensions?.balance_sheet],
                  ['Business quality', score?.dimensions?.business_quality],
                  ['Risk', score?.dimensions?.risk]
                ].map(([label, value]) => {
                  const val = typeof value === 'number' ? value.toFixed(0) : "N/A";
                  return (
                    <div className="metric-row" key={String(label)} style={{ padding: "12px 0", borderBottom: "1px solid var(--line)", fontSize: 14, display: "flex", justifyContent: "space-between" }}>
                      <span>{label}</span>
                      <b style={{ color: "var(--ink)" }}>{val !== "N/A" ? `${val}/100` : "N/A"}</b>
                    </div>
                  );
                })}
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
              <div className="metric-grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
                {metricLabels.map(([label, value]) => (
                  <div className="metric" key={label} style={{ background: "var(--surface)", padding: 16, borderRadius: 8 }}>
                    <span className="label" style={{ fontSize: 12, color: "var(--muted)", display: "block", marginBottom: 4 }}>{label}</span>
                    <b style={{ fontSize: 20 }}>{value}</b>
                  </div>
                ))}
              </div>
              
              <div className="panel" style={{ flex: 1 }}>
                <h2 style={{ fontSize: 16, marginBottom: 16 }}>Top Risks</h2>
                {risks.slice(0, 3).map(r => (
                  <div key={r.id} style={{ marginBottom: 16, paddingBottom: 16, borderBottom: "1px solid var(--line)" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <b style={{ fontSize: 14 }}>{r.category}</b>
                      <span className={`status-badge ${r.severity.toLowerCase() === 'high' ? 'upcoming' : 'ongoing'}`} style={{ fontSize: 11, padding: "2px 6px" }}>{r.severity}</span>
                    </div>
                    <p style={{ fontSize: 13, color: "var(--muted)", margin: 0 }}>{r.summary}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === "Financials" && (
          <div className="panel">
            <div className="section-title">
              <h2>Financial trajectory</h2>
              <span className="chip">INR crore</span>
            </div>
            <table className="table" style={{ width: "100%", textAlign: "left", borderCollapse: "collapse", marginBottom: 32 }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--line)" }}>
                  <th style={{ padding: "12px 8px", color: "var(--dimmed)", fontWeight: 500 }}>Period</th>
                  <th style={{ padding: "12px 8px", color: "var(--dimmed)", fontWeight: 500 }}>Revenue</th>
                  <th style={{ padding: "12px 8px", color: "var(--dimmed)", fontWeight: 500 }}>EBITDA</th>
                  <th style={{ padding: "12px 8px", color: "var(--dimmed)", fontWeight: 500 }}>PAT</th>
                  <th style={{ padding: "12px 8px", color: "var(--dimmed)", fontWeight: 500 }}>EBITDA margin</th>
                </tr>
              </thead>
              <tbody>
                {financials?.items?.map((row: Any) => (
                  <tr key={row.fiscal_year} style={{ borderBottom: "1px solid var(--line)" }}>
                    <td style={{ padding: "12px 8px" }}>{row.fiscal_year}</td>
                    <td style={{ padding: "12px 8px" }}>{n(row.revenue)}</td>
                    <td style={{ padding: "12px 8px" }}>{n(row.ebitda)}</td>
                    <td style={{ padding: "12px 8px" }}>{n(row.pat)}</td>
                    <td style={{ padding: "12px 8px" }}>{n(row.ebitda_margin, '%')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <FinancialChart items={financials?.items || []} />
          </div>
        )}

        {activeTab === "Valuation" && (
          <div className="panel">
            <div className="section-title">
              <h2>Valuation snapshot</h2>
              <span className="chip">{valuation?.CURRENT_MARKET ? "Current Market" : "IPO at issue (upper band)"}</span>
            </div>
            <div className="metric-grid" style={{ gridTemplateColumns: "repeat(4, 1fr)" }}>
              {[
                ['Market cap', n(valuation?.CURRENT_MARKET?.market_cap || valuation?.IPO_AT_ISSUE?.upper_band?.implied_market_cap)],
                ['Enterprise value', n(valuation?.CURRENT_MARKET?.enterprise_value || valuation?.IPO_AT_ISSUE?.upper_band?.enterprise_value)],
                ['P/S', n(valuation?.CURRENT_MARKET?.ps || valuation?.IPO_AT_ISSUE?.upper_band?.ps, 'x')],
                ['EV / EBITDA', n(valuation?.CURRENT_MARKET?.ev_ebitda || valuation?.IPO_AT_ISSUE?.upper_band?.ev_ebitda, 'x')]
              ].map(([label, value]) => (
                <div className="metric" key={String(label)} style={{ background: "var(--surface)", padding: 20, borderRadius: 8 }}>
                  <span className="label" style={{ display: "block", marginBottom: 8, color: "var(--muted)", fontSize: 13 }}>{label}</span>
                  <b style={{ fontSize: "1.5rem" }}>{value}</b>
                </div>
              ))}
            </div>
            <p style={{ marginTop: 24, fontSize: 14, color: "var(--muted)" }}>
              The valuation engine presents the multiple and peer context; it does not decide whether a premium is justified.
            </p>
          </div>
        )}

        {activeTab === "Peers" && (
          <PeerComparison ipoId={Number(params.id)} />
        )}

        {activeTab === "Risks" && (
          <div className="panel">
            <h2>Key risks</h2>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24, marginTop: 24 }}>
              {risks.map(r => (
                <div className="risk" key={r.id} style={{ background: "var(--surface)", padding: 20, borderRadius: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                    <span className={`label status-badge ${r.severity.toLowerCase() === 'high' ? 'upcoming' : 'ongoing'}`}>
                      {r.severity}
                    </span>
                    <span style={{ fontSize: 12, color: "var(--dimmed)", display: "flex", alignItems: "center", gap: 4 }}>
                      <FileText size={12} /> p.{r.source_page}
                    </span>
                  </div>
                  <div style={{ fontWeight: 600, color: "var(--ink)", marginBottom: 8 }}>{r.category}</div>
                  <p style={{ fontSize: 13, margin: 0, color: "var(--muted)", lineHeight: 1.5 }}>{r.summary}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "DCF" && (
          <DCFCalculator 
            initialRevenue={financials?.items?.at(-1)?.revenue} 
            initialMargin={financials?.items?.at(-1)?.ebitda_margin} 
          />
        )}

        {activeTab === "Research" && (
          <div className="panel research glass-panel">
            <div className="section-title">
              <div>
                <div className="eyebrow">Evidence-first agent</div>
                <h2>Research workspace</h2>
              </div>
              <span className="chip">Contextual</span>
            </div>
            <p style={{ color: "var(--muted)" }}>Ask within this company context. Structured tools retrieve financial facts; filing references support factual claims.</p>
            
            <div className="input-row" style={{ display: "flex", gap: 12, marginTop: 24 }}>
              <input 
                style={{ flex: 1, padding: "12px 16px", background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 8, color: "var(--ink)" }}
                value={question} 
                onChange={e => setQuestion(e.target.value)} 
                onKeyDown={e => e.key === 'Enter' && ask()} 
                placeholder="Ask a question about this IPO..."
              />
              <button className="button" onClick={ask} disabled={busy} style={{ padding: "0 24px" }}>
                {busy ? "Researching…" : <><Send size={15} style={{ marginRight: 8 }}/> Ask agent</>}
              </button>
            </div>
            
            {error && <p style={{ color: 'var(--red)', marginTop: 12 }}>{error}</p>}
            
            {answer && (
              <div className="message" style={{ animation: "fadeInUp 0.4s ease-out", marginTop: 32, background: "rgba(68, 215, 209, 0.05)", padding: 24, borderRadius: 8, border: "1px solid rgba(68, 215, 209, 0.2)" }}>
                <b style={{ color: "var(--cyan)", display: "block", marginBottom: 12, fontSize: 16 }}>Research answer</b>
                <p style={{ color: 'var(--ink)', margin: "0 0 16px", lineHeight: 1.6 }}>{answer.answer}</p>
                
                <div className="label" style={{ marginBottom: 16, fontSize: 13, color: "var(--dimmed)" }}>
                  Tools used: <span style={{ color: "var(--gold)" }}>{answer.tool_trace.join(" → ")}</span>
                </div>
                
                {answer.claims && answer.claims.length > 0 && (
                  <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                    {answer.claims.map((claim: any, index: number) => (
                      <div className="claim-box" key={index} style={{ padding: "16px", background: "var(--bg)", borderRadius: "8px", border: "1px solid var(--line)" }}>
                        <div style={{ color: "var(--ink)", marginBottom: 8, fontWeight: 500 }}>{claim.text}</div>
                        {claim.citations && claim.citations.map((cite: any, cidx: number) => (
                          <div className="citation" key={cidx} style={{ marginTop: 8, paddingLeft: 12, borderLeft: "2px solid var(--cyan)" }}>
                            <div style={{ fontSize: 12, fontWeight: 600, color: "var(--dimmed)", marginBottom: 4 }}>
                              Source · Document {cite.document_id}, Page {cite.page} {cite.section ? `(${cite.section})` : ""}
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
        )}

        {activeTab === "Filings" && (
          <div className="panel" style={{ padding: 48, textAlign: "center" }}>
            <FileText size={48} color="var(--dimmed)" style={{ margin: "0 auto 16px", opacity: 0.5 }} />
            <h3 style={{ fontSize: 18, marginBottom: 8 }}>No filings processed</h3>
            <p style={{ color: "var(--muted)", maxWidth: 400, margin: "0 auto" }}>
              Filing documents and DRHPs for this company have not been uploaded or processed by the system yet.
            </p>
          </div>
        )}

      </section>
    </main>
  );
}
