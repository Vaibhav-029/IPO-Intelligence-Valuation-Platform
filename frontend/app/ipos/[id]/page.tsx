"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Bookmark, ChevronLeft, Send, ShieldCheck, FileText } from "lucide-react";
import { apiFetch, getIPO } from "../../../lib/api";
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
    ['IPO score', n(score?.overall_score, '/10')]
  ];

  return (
    <main style={{ animation: "fadeIn 0.5s ease-out" }}>
      <section className="detail-header">
        <Link className="back" href="/"><ChevronLeft size={15}/> Back to directory</Link>
        <div className="detail-title">
          <div>
            <div className="eyebrow">{ipo.sector} · {ipo.status}</div>
            <h1>{ipo.name}</h1>
            <p>{ipo.description}</p>
          </div>
          <button 
            className="button secondary" 
            onClick={handleSave}
            disabled={saved}
          >
            <Bookmark size={16}/> {saved ? "Saved to watchlist" : "Save research"}
          </button>
        </div>
      </section>

      <section className="metric-grid" style={{ animation: "fadeInUp 0.6s ease-out" }}>
        {metricLabels.map(([label, value]) => (
          <div className="metric" key={label}>
            <span className="label">{label}</span>
            <b>{value}</b>
          </div>
        ))}
      </section>

      <section className="layout" style={{ animation: "fadeInUp 0.8s ease-out" }}>
        <div className="panel glass-panel">
          <div className="section-title">
            <h2>Financial trajectory</h2>
            <span className="chip">INR crore</span>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Period</th>
                <th>Revenue</th>
                <th>EBITDA</th>
                <th>PAT</th>
                <th>EBITDA margin</th>
              </tr>
            </thead>
            <tbody>
              {financials?.items?.map((row: Any) => (
                <tr key={row.fiscal_year}>
                  <td>{row.fiscal_year}</td>
                  <td>{n(row.revenue)}</td>
                  <td>{n(row.ebitda)}</td>
                  <td>{n(row.pat)}</td>
                  <td>{n(row.ebitda_margin, '%')}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <FinancialChart items={financials?.items || []} />
        </div>

        <aside className="panel glass-panel">
          <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <ShieldCheck color="var(--cyan)" size={20}/> Scorecard
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
                <div className="metric-row" key={String(label)} style={{ padding: "12px 0", borderBottom: "1px solid var(--line)", fontSize: 14 }}>
                  <span>{label}</span>
                  <b style={{ color: "var(--ink)" }}>{val !== "N/A" ? `${val}/100` : "N/A"}</b>
                </div>
              );
            })}
            
            {score?.coverage && score?.coverage.overall_effective_weight < 100 && (
              <div style={{ marginTop: 12, padding: 8, background: "var(--surface)", borderRadius: 6, fontSize: 12, color: "var(--dimmed)" }}>
                <b>Note:</b> Score redistributed (Effective coverage: {score.coverage.overall_effective_weight}%)
              </div>
            )}
            
            {score?.explanations && (
              <div style={{ marginTop: 16 }}>
                <h4 style={{ fontSize: 13, marginBottom: 8 }}>Methodology Notes</h4>
                {Object.entries(score.explanations).map(([k, v]) => (
                  <div key={k} style={{ fontSize: 12, color: "var(--dimmed)", marginBottom: 4 }}>
                    <b style={{textTransform: 'capitalize'}}>{k.replace('_', ' ')}:</b> {String(v)}
                  </div>
                ))}
              </div>
            )}
          </div>
        </aside>

        <div className="panel glass-panel">
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
              <div className="metric" key={String(label)}>
                <span className="label">{label}</span>
                <b style={{ fontSize: "1.25rem" }}>{value}</b>
              </div>
            ))}
          </div>
          <p style={{ marginTop: 24, fontSize: 14, color: "var(--muted)" }}>
            The valuation engine presents the multiple and peer context; it does not decide whether a premium is justified.
          </p>
        </div>

        <DCFCalculator 
          initialRevenue={financials?.items?.at(-1)?.revenue} 
          initialMargin={financials?.items?.at(-1)?.ebitda_margin} 
        />

        <PeerComparison ipoId={Number(params.id)} />

        <aside className="panel glass-panel">
          <h2>Key risks</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 16 }}>
            {risks.map(r => (
              <div className="risk" key={r.id}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <span className={`label status-badge ${r.severity.toLowerCase() === 'high' ? 'upcoming' : 'ongoing'}`}>
                    {r.severity}
                  </span>
                  <span style={{ fontSize: 12, color: "var(--dimmed)", display: "flex", alignItems: "center", gap: 4 }}>
                    <FileText size={12} /> p.{r.source_page}
                  </span>
                </div>
                <div style={{ marginTop: 12, fontWeight: 600, color: "var(--ink)" }}>{r.category}</div>
                <p style={{ fontSize: 13, margin: "6px 0 0", color: "var(--muted)", lineHeight: 1.5 }}>{r.summary}</p>
              </div>
            ))}
          </div>
        </aside>

        <div className="panel research glass-panel" style={{ gridColumn: "1 / -1" }}>
          <div className="section-title">
            <div>
              <div className="eyebrow">Evidence-first agent</div>
              <h2>Research workspace</h2>
            </div>
            <span className="chip">Not financial advice</span>
          </div>
          <p>Ask within this company context. Structured tools retrieve financial facts; filing references support factual claims.</p>
          
          <div className="input-row">
            <input 
              value={question} 
              onChange={e => setQuestion(e.target.value)} 
              onKeyDown={e => e.key === 'Enter' && ask()} 
              placeholder="Ask a question about this IPO..."
            />
            <button className="button" onClick={ask} disabled={busy}>
              {busy ? "Researching…" : <><Send size={15}/> Ask agent</>}
            </button>
          </div>
          
          {error && <p style={{ color: 'var(--red)', marginTop: 12 }}>{error}</p>}
          
          {answer && (
            <div className="message" style={{ animation: "fadeInUp 0.4s ease-out" }}>
              <b style={{ color: "var(--cyan)", display: "block", marginBottom: 12 }}>Research answer</b>
              <p style={{ color: 'var(--ink)', margin: "0 0 16px", lineHeight: 1.6 }}>{answer.answer}</p>
              
              <div className="label" style={{ marginBottom: 16 }}>
                Tools used: <span style={{ color: "var(--gold)" }}>{answer.tool_trace.join(" → ")}</span>
              </div>
              
              {answer.claims && answer.claims.length > 0 && (
                <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                  {answer.claims.map((claim: any, index: number) => (
                    <div className="claim-box" key={index} style={{ padding: "12px", background: "rgba(255,255,255,0.03)", borderRadius: "8px", border: "1px solid rgba(255,255,255,0.1)" }}>
                      <div style={{ color: "var(--ink)", marginBottom: 8, fontWeight: 500 }}>{claim.text}</div>
                      {claim.citations && claim.citations.map((cite: any, cidx: number) => (
                        <div className="citation" key={cidx} style={{ marginTop: 8, paddingLeft: 8, borderLeft: "2px solid var(--cyan)" }}>
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
      </section>
    </main>
  );
}
