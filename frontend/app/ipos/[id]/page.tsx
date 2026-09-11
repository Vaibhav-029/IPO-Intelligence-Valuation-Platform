"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { 
  Bookmark, 
  ChevronLeft, 
  Send, 
  ShieldCheck, 
  FileText, 
  TrendingUp, 
  AlertTriangle,
  Layers,
  ArrowUpRight,
  ExternalLink,
  Info,
  Users,
  Calculator
} from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip
} from "recharts";
import { apiFetch, getIPO } from "../../../lib/api";
import { date, priceBand, issueSize, scoreOutOfTen } from "../../../lib/format";
import ScoreRadial from "../../../components/ScoreRadial";
import Shimmer from "../../../components/Shimmer";
import FinancialChart from "../../../components/FinancialChart";
import { useAuth } from "../../../lib/AuthContext";

type Any = Record<string, any>;

// Safe numeric formatter — strictly follows DATA RULES: unknown/null -> "—"
function n(value: any, suffix = "", decimals = 2): string {
  if (value === null || value === undefined || value === "" || Number.isNaN(Number(value))) {
    return "—";
  }
  const num = Number(value);
  return `${num.toLocaleString("en-IN", { 
    minimumFractionDigits: Number.isInteger(num) ? 0 : decimals, 
    maximumFractionDigits: decimals 
  })}${suffix}`;
}

function formatMultiple(val: any): string {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  return `${Number(val).toFixed(1)}x`;
}

function formatPremium(val: any) {
  if (val === null || val === undefined || Number.isNaN(Number(val))) return "—";
  const num = Number(val);
  const color = num > 0 ? "text-[#b91c1c]" : num < 0 ? "text-[#15803d]" : "text-[#64748b]";
  const prefix = num > 0 ? "+" : "";
  return <span className={`font-mono font-semibold ${color}`}>{prefix}{num.toFixed(1)}%</span>;
}

function getInitials(name: string): string {
  if (!name) return "—";
  const words = name.trim().split(/\s+/);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.substring(0, 2).toUpperCase();
}

export default function IPOPage() {
  const params = useParams<{ id: string }>(); 
  const id = Number(params.id); 
  const { user, setAuthModalOpen } = useAuth();
  
  const [ipo, setIpo] = useState<Any | null>(null); 
  const [financials, setFinancials] = useState<Any | null>(null); 
  const [valuation, setValuation] = useState<Any | null>(null); 
  const [score, setScore] = useState<Any | null>(null); 
  const [risks, setRisks] = useState<Any[]>([]); 
  const [peersData, setPeersData] = useState<Any | null>(null);
  
  // Research state
  const [question, setQuestion] = useState("Why is this IPO valued at a premium to peers?"); 
  const [answer, setAnswer] = useState<Any | null>(null); 
  const [busy, setBusy] = useState(false); 
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState("Overview");

  // DCF state
  const [dcfMargin, setDcfMargin] = useState(15);
  const [dcfGrowth, setDcfGrowth] = useState(15);
  const [dcfDiscount, setDcfDiscount] = useState(12);
  const [dcfTerminal, setDcfTerminal] = useState(5);
  const [dcfTax, setDcfTax] = useState(25);
  const [dcfDaPct, setDcfDaPct] = useState(5);
  const [dcfCapexPct, setDcfCapexPct] = useState(3);
  const [dcfNwcPct, setDcfNwcPct] = useState(2);
  const [dcfResult, setDcfResult] = useState<Any | null>(null);
  const [dcfLoading, setDcfLoading] = useState(false);
  const [dcfError, setDcfError] = useState("");

  useEffect(() => { 
    if (!id || Number.isNaN(id)) return;
    setLoading(true);

    Promise.all([
      getIPO(id),
      apiFetch(`/ipos/${id}/financials`).catch(() => null),
      apiFetch(`/ipos/${id}/valuation`).catch(() => null),
      apiFetch(`/ipos/${id}/score`).catch(() => null),
      apiFetch(`/ipos/${id}/risks`).catch(() => []),
      apiFetch(`/ipos/${id}/peers`).catch(() => null)
    ])
    .then(([a, b, c, d, e, f]) => {
      setIpo(a);
      setFinancials(b);
      setValuation(c);
      setScore(d);
      setRisks(Array.isArray(e) ? e : []);
      setPeersData(f);
      setLoading(false);
    })
    .catch(e => {
      setError(e.message);
      setLoading(false);
    }); 
  }, [id]);

  // Synchronize initial DCF margin when financials load
  useEffect(() => {
    if (financials?.items?.length) {
      const latestMargin = financials.items[financials.items.length - 1].ebitda_margin;
      if (latestMargin != null && latestMargin > 0) {
        setDcfMargin(Math.min(50, Math.max(5, Math.round(latestMargin * 10) / 10)));
      }
    }
  }, [financials]);

  // Debounced DCF calculation
  useEffect(() => {
    if (!id || Number.isNaN(id) || activeTab !== "DCF") return;
    let active = true;
    const fetchDCF = async () => {
      setDcfLoading(true);
      setDcfError("");
      try {
        const payload = {
          revenue_growth_rate: dcfGrowth / 100,
          ebitda_margin: dcfMargin / 100,
          tax_rate: dcfTax / 100,
          d_and_a_pct_of_revenue: dcfDaPct / 100,
          capex_pct_of_revenue: dcfCapexPct / 100,
          change_in_nwc_pct_of_revenue: dcfNwcPct / 100,
          discount_rate: dcfDiscount / 100,
          terminal_growth_rate: dcfTerminal / 100,
          years: 5
        };
        const res = await apiFetch(`/ipos/${id}/dcf`, {
          method: "POST",
          body: JSON.stringify(payload)
        });
        if (active) setDcfResult(res);
      } catch (e: any) {
        if (active) setDcfError(e.message || "Failed to calculate DCF");
      } finally {
        if (active) setDcfLoading(false);
      }
    };

    const timer = setTimeout(fetchDCF, 300);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id, activeTab, dcfMargin, dcfGrowth, dcfDiscount, dcfTerminal, dcfTax, dcfDaPct, dcfCapexPct, dcfNwcPct]);

  const dcfChartData = dcfResult?.projections?.map((cf: any) => ({
    name: `Year ${cf.year}`,
    fcff: cf.fcff,
    present_value: cf.present_value,
  })) || [];

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
      setError(e.message || "Failed to query research agent."); 
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

  if (error && !ipo) {
    return (
      <main className="market-page-container">
        <div className="section-container" style={{ textAlign: "center", padding: "48px 24px" }}>
          <p style={{ color: "var(--badge-upcoming-text)", fontSize: 14, fontWeight: 500 }}>{error}</p>
          <Link className="btn-signin" href="/" style={{ marginTop: 16, display: "inline-flex" }}>
            ← Back to Market Feed
          </Link>
        </div>
      </main>
    ); 
  }
  
  if (loading || !ipo) {
    return (
      <main className="market-page-container">
        <Shimmer />
      </main>
    );
  }

  const currentValuation = 
    valuation?.CURRENT_MARKET || 
    valuation?.IPO_AT_ISSUE?.upper_band || 
    (valuation?.market_cap ? valuation : null);

  const upperCap = currentValuation?.market_cap ? n(Math.round(currentValuation.market_cap)) : "—";
  const ev = currentValuation?.enterprise_value ? n(Math.round(currentValuation.enterprise_value)) : "—";

  // Score dimensions matching backend methodology
  const scoreBreakdown = [
    { label: "Financial Quality", key: "financial_quality", weight: "20%" },
    { label: "Growth", key: "growth", weight: "20%" },
    { label: "Valuation", key: "valuation", weight: "20%" },
    { label: "Balance Sheet", key: "balance_sheet", weight: "15%" },
    { label: "Business Quality", key: "business_quality", weight: "15%" },
    { label: "Risk Assessment", key: "risk", weight: "10%" },
  ];

  // Financial summary items
  const finItems = financials?.items || [];

  return (
    <main className="min-h-screen bg-[#f8fafc] text-[#0f172a] pb-16 font-sans">
      <div className="max-w-[1320px] mx-auto px-4 sm:px-6 pt-5">
        
        {/* BREADCRUMB & METADATA STRIP */}
        <div className="flex flex-wrap items-center justify-between text-xs text-[#64748b] mb-4 gap-2">
          <div className="flex items-center gap-1.5 font-sans">
            <Link href="/" className="hover:text-[#0f2942] transition-colors">Market</Link>
            <span>/</span>
            <span>{ipo.listing_segment === "SME" ? "SME Growth" : "Mainboard Equity"}</span>
            <span>/</span>
            <span className="text-[#001428] font-medium">{ipo.name} ({ipo.exchange || "NSE / BSE"})</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-[#10b981] inline-block animate-pulse"></span>
            <span className="font-mono text-[11px] uppercase tracking-wider text-[#475569]">LIVE FEED: NSE/BSE BOOK RUNNER CONSOLE</span>
          </div>
        </div>

        {/* PRIMARY HEADER & IDENTITY STRIP */}
        <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 mb-5 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            
            {/* Left: Company Identity */}
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-[2px] border border-[#e2e8f0] bg-[#f8fafc] flex items-center justify-center font-bold text-sm text-[#001428] shrink-0 font-mono">
                {ipo.logo_url ? (
                  <img src={ipo.logo_url} alt={ipo.name} className="w-full h-full object-contain p-1" />
                ) : (
                  getInitials(ipo.name)
                )}
              </div>
              
              <div>
                <div className="flex flex-wrap items-center gap-2.5">
                  <h1 className="text-2xl font-bold text-[#001428] tracking-tight">{ipo.name}</h1>
                  <span className="px-2 py-0.5 text-[11px] font-mono font-medium text-[#475569] bg-[#f1f5f9] border border-[#e2e8f0] rounded-[2px]">
                    {ipo.exchange || "NSE / BSE"} {ipo.listing_segment?.toUpperCase() || "MAINBOARD"}
                  </span>
                  
                  {/* Status Badge */}
                  {ipo.status === "Ongoing" && (
                    <span className="px-2 py-0.5 text-[11px] font-mono font-semibold text-[#15803d] bg-[#f0fdf4] border border-[#bbf7d0] rounded-[2px] flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#16a34a]"></span>
                      ONGOING
                    </span>
                  )}
                  {ipo.status === "Upcoming" && (
                    <span className="px-2 py-0.5 text-[11px] font-mono font-semibold text-[#b45309] bg-[#fefce8] border border-[#fde68a] rounded-[2px] flex items-center gap-1">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#d97706]"></span>
                      UPCOMING
                    </span>
                  )}
                  {ipo.status === "Listed" && (
                    <span className="px-2 py-0.5 text-[11px] font-mono font-semibold text-[#1d4ed8] bg-[#eff6ff] border border-[#bfdbfe] rounded-[2px]">
                      LISTED
                    </span>
                  )}
                  {ipo.status === "Closed" && (
                    <span className="px-2 py-0.5 text-[11px] font-mono font-semibold text-[#475569] bg-[#f8fafc] border border-[#cbd5e1] rounded-[2px]">
                      CLOSED
                    </span>
                  )}
                </div>

                <p className="text-xs text-[#64748b] mt-1.5 max-w-3xl line-clamp-2 leading-relaxed">
                  {ipo.description || `${ipo.name} issue details, financial statements, valuation framework, and risk factors.`}
                </p>
              </div>
            </div>

            {/* Right: Actions */}
            <div className="flex items-center gap-2.5 shrink-0 self-start lg:self-center">
              <button 
                className={`h-8 px-3.5 inline-flex items-center gap-1.5 text-xs font-medium border rounded-[2px] transition-colors ${
                  saved 
                    ? "bg-[#f1f5f9] text-[#0f2942] border-[#cbd5e1]" 
                    : "bg-white text-[#334155] border-[#cbd5e1] hover:bg-[#f8fafc]"
                }`}
                onClick={handleSave}
              >
                <Bookmark size={13} className={saved ? "fill-current" : ""} />
                <span>{saved ? "Tracked" : "Track Issue"}</span>
              </button>

              <Link 
                href="/" 
                className="h-8 px-3.5 inline-flex items-center gap-1 text-xs font-semibold bg-[#0f2942] text-white rounded-[2px] hover:bg-[#1e3a8a] transition-colors"
              >
                <ChevronLeft size={14} />
                <span>Market Feed</span>
              </Link>
            </div>

          </div>
        </div>

        {/* SUMMARY METRICS STRIP (7 Bento Cards) */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2.5 mb-5">
          
          <div className="bg-white border border-[#e2e8f0] p-3 rounded-[2px]">
            <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Status</div>
            <div className="text-xs font-bold text-[#001428]">
              {ipo.status === "Ongoing" && <span className="text-[#15803d]">ONGOING</span>}
              {ipo.status === "Upcoming" && <span className="text-[#b45309]">UPCOMING</span>}
              {ipo.status === "Listed" && <span className="text-[#1d4ed8]">LISTED</span>}
              {ipo.status === "Closed" && <span className="text-[#475569]">CLOSED</span>}
              {!ipo.status && "—"}
            </div>
          </div>

          <div className="bg-white border border-[#e2e8f0] p-3 rounded-[2px]">
            <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Price Band</div>
            <div className="text-xs font-mono font-bold text-[#001428]">{priceBand(ipo.price_band)}</div>
          </div>

          <div className="bg-white border border-[#e2e8f0] p-3 rounded-[2px]">
            <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Issue Size</div>
            <div className="text-xs font-mono font-bold text-[#001428]">{issueSize(ipo.issue_size_crore ?? ipo.issue_size)}</div>
          </div>

          <div className="bg-white border border-[#e2e8f0] p-3 rounded-[2px]">
            <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Bidding Dates</div>
            <div className="text-xs font-mono font-medium text-[#001428]">
              {ipo.open_date ? date(ipo.open_date) : "—"}
              {ipo.close_date && ` – ${date(ipo.close_date)}`}
            </div>
          </div>

          <div className="bg-white border border-[#e2e8f0] p-3 rounded-[2px]">
            <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Lot Size / Min App</div>
            <div className="text-xs font-mono font-medium text-[#001428]">
              {ipo.lot_size ? (
                <span>
                  {ipo.lot_size} Shares{ipo.min_investment ? ` (₹${n(ipo.min_investment)})` : ""}
                </span>
              ) : "—"}
            </div>
          </div>

          <div className="bg-white border border-[#e2e8f0] p-3 rounded-[2px]">
            <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Listing Date</div>
            <div className="text-xs font-mono font-medium text-[#001428]">{date(ipo.listing_date)}</div>
          </div>

          <div className="bg-white border border-[#e2e8f0] p-3 rounded-[2px] col-span-2 md:col-span-4 lg:col-span-1">
            <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Analyst Score</div>
            <div className="text-xs font-mono font-bold text-[#001428]">
              {score?.overall_score != null ? (
                scoreOutOfTen(score.overall_score)
              ) : (
                <span className="text-[11px] font-sans font-medium text-[#64748b]">Insufficient Data</span>
              )}
            </div>
          </div>

        </div>

        {/* HORIZONTAL TAB NAVIGATION BAR */}
        <div className="bg-white border border-[#e2e8f0] rounded-[2px] px-3 mb-5 shadow-sm">
          <div className="flex items-center overflow-x-auto scrollbar-none gap-6 text-xs font-medium">
            {[
              { id: "Overview", label: "Overview" },
              { id: "Financials", label: "Financials" },
              { id: "Valuation", label: "Valuation" },
              { id: "Peers", label: "Peers" },
              { id: "Risks", label: "Risks" },
              { id: "DCF", label: "DCF" },
              { id: "Research", label: "Research" },
              { id: "Filings", label: "Filings" },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`py-3 border-b-2 whitespace-nowrap transition-all ${
                  activeTab === tab.id
                    ? "border-[#001428] text-[#001428] font-bold"
                    : "border-transparent text-[#64748b] hover:text-[#0f172a] hover:border-[#cbd5e1]"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* TAB 1: OVERVIEW */}
        {activeTab === "Overview" && (
          <div className="space-y-5">
            {/* Top Row: Deal Stats Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              
              <div className="bg-white border border-[#e2e8f0] p-4 rounded-[2px] shadow-sm">
                <div className="flex items-center justify-between text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-2">
                  <span>Upper Band Valuation</span>
                  <span className="font-mono text-[#0f2942]">CAP</span>
                </div>
                <div className="text-lg font-bold text-[#001428] font-mono">
                  {upperCap !== "—" ? `₹${upperCap} Cr` : "—"}
                </div>
                <div className="text-xs text-[#64748b] mt-1 flex justify-between">
                  <span>Enterprise Value</span>
                  <span className="font-mono font-medium text-[#001428]">{ev !== "—" ? `₹${ev} Cr` : "—"}</span>
                </div>
              </div>

              <div className="bg-white border border-[#e2e8f0] p-4 rounded-[2px] shadow-sm">
                <div className="flex items-center justify-between text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-2">
                  <span>Issue Tranche Split</span>
                  <span className="font-mono text-[#0f2942]">CAPITAL</span>
                </div>
                <div className="text-lg font-bold text-[#001428] font-mono">
                  {(ipo.fresh_issue_crore ?? ipo.fresh_issue_size) != null ? `₹${n(ipo.fresh_issue_crore ?? ipo.fresh_issue_size)} Cr Fresh` : "—"}
                </div>
                <div className="text-xs text-[#64748b] mt-1 flex justify-between">
                  <span>Offer for Sale (OFS)</span>
                  <span className="font-mono font-medium text-[#001428]">
                    {(ipo.ofs_crore ?? ipo.ofs_issue_size) != null ? `₹${n(ipo.ofs_crore ?? ipo.ofs_issue_size)} Cr` : "—"}
                  </span>
                </div>
              </div>

              <div className="bg-white border border-[#e2e8f0] p-4 rounded-[2px] shadow-sm">
                <div className="flex items-center justify-between text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-2">
                  <span>Issue Schedule</span>
                  <span className="font-mono text-[#0369a1]">TIMELINE</span>
                </div>
                <div className="text-sm font-semibold text-[#001428] font-mono">
                  Open: {date(ipo.open_date)}
                </div>
                <div className="text-xs text-[#64748b] mt-1 flex justify-between">
                  <span>Close: {date(ipo.close_date)}</span>
                  <span>List: {date(ipo.listing_date)}</span>
                </div>
              </div>

              <div className="bg-white border border-[#e2e8f0] p-4 rounded-[2px] shadow-sm">
                <div className="flex items-center justify-between text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-2">
                  <span>Analyst Rating</span>
                  <span className="font-mono text-[#15803d]">CONSENSUS</span>
                </div>
                <div className="text-lg font-bold text-[#001428] font-mono">
                  {score?.overall_score != null ? scoreOutOfTen(score.overall_score) : <span className="text-sm font-sans font-medium text-[#64748b]">Unrated</span>}
                </div>
                <div className="text-xs text-[#64748b] mt-1 flex justify-between">
                  <span>Methodology</span>
                  <span className="font-mono text-[#475569]">v{score?.methodology_version || "4.0"}</span>
                </div>
              </div>

            </div>

            {/* Second Row: Audited Condensed Financials + Scorecard Dimensions */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
              
              {/* Financial Summary Table (7 cols) */}
              <div className="lg:col-span-7 bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
                <div className="flex items-center justify-between pb-3 border-b border-[#f1f5f9] mb-4">
                  <div>
                    <h2 className="font-bold text-sm text-[#001428]">Condensed Financial Performance &amp; Unit Economics</h2>
                    <p className="text-xs text-[#64748b]">Audited metrics sourced from Consolidated Statements (in ₹ Crores)</p>
                  </div>
                  <span className="text-[11px] font-mono text-[#475569] bg-[#f8fafc] px-2 py-0.5 border border-[#e2e8f0] rounded-[2px]">
                    CONSOLIDATED
                  </span>
                </div>

                {finItems.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="border-b border-[#e2e8f0] text-[#64748b]">
                          <th className="py-2 px-2 font-semibold">FINANCIAL METRIC</th>
                          {finItems.map((fi: Any, idx: number) => (
                            <th key={fi.id || fi.fiscal_year || idx} className="py-2 px-2 text-right font-semibold font-mono">
                              {fi.fiscal_year}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#f1f5f9]">
                        <tr>
                          <td className="py-2 px-2 text-[#334155] font-medium">Revenue from Operations</td>
                          {finItems.map((fi: Any, idx: number) => (
                            <td key={`rev-${fi.id || fi.fiscal_year || idx}`} className="py-2 px-2 text-right font-mono text-[#001428]">
                              {n(fi.revenue)}
                            </td>
                          ))}
                        </tr>
                        <tr>
                          <td className="py-2 px-2 text-[#334155] font-medium">EBITDA</td>
                          {finItems.map((fi: Any, idx: number) => (
                            <td key={`ebitda-${fi.id || fi.fiscal_year || idx}`} className={`py-2 px-2 text-right font-mono ${fi.ebitda < 0 ? "text-[#b91c1c]" : "text-[#001428]"}`}>
                              {n(fi.ebitda)}
                            </td>
                          ))}
                        </tr>
                        <tr>
                          <td className="py-2 px-2 text-[#334155] font-medium">EBITDA Margin</td>
                          {finItems.map((fi: Any, idx: number) => (
                            <td key={`margin-${fi.id || fi.fiscal_year || idx}`} className={`py-2 px-2 text-right font-mono ${fi.ebitda_margin < 0 ? "text-[#b91c1c]" : "text-[#001428]"}`}>
                              {n(fi.ebitda_margin, "%", 1)}
                            </td>
                          ))}
                        </tr>
                        <tr>
                          <td className="py-2 px-2 text-[#334155] font-medium">PAT / Net Profit (Loss)</td>
                          {finItems.map((fi: Any, idx: number) => (
                            <td key={`pat-${fi.id || fi.fiscal_year || idx}`} className={`py-2 px-2 text-right font-mono ${fi.pat < 0 ? "text-[#b91c1c]" : "text-[#001428]"}`}>
                              {n(fi.pat)}
                            </td>
                          ))}
                        </tr>
                        <tr>
                          <td className="py-2 px-2 text-[#334155] font-medium">Total Equity / Net Worth</td>
                          {finItems.map((fi: Any, idx: number) => (
                            <td key={`equity-${fi.id || fi.fiscal_year || idx}`} className="py-2 px-2 text-right font-mono text-[#001428]">
                              {n(fi.equity ?? fi.total_equity)}
                            </td>
                          ))}
                        </tr>
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="py-12 text-center text-xs text-[#64748b]">
                    Detailed historical financial statements are being processed for this issuer.
                  </div>
                )}

                {/* Key Financial Highlights 4-Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-5 pt-4 border-t border-[#f1f5f9]">
                  <div className="p-2.5 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">REVENUE CAGR (2Y)</div>
                    <div className="text-xs font-mono font-bold text-[#001428]">
                      {(financials?.revenue_cagr_2y ?? financials?.growth_cagr_2y) != null ? `${(financials?.revenue_cagr_2y ?? financials?.growth_cagr_2y).toFixed(1)}%` : "—"}
                    </div>
                  </div>
                  <div className="p-2.5 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">LATEST EBITDA MARGIN</div>
                    <div className="text-xs font-mono font-bold text-[#001428]">
                      {finItems.length > 0 ? n(finItems[finItems.length - 1].ebitda_margin, "%", 1) : "—"}
                    </div>
                  </div>
                  <div className="p-2.5 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">P/E MULTIPLE</div>
                    <div className="text-xs font-mono font-bold text-[#001428]">
                      {currentValuation?.pe ? `${currentValuation.pe.toFixed(1)}x` : "—"}
                    </div>
                  </div>
                  <div className="p-2.5 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">IPO SCORE</div>
                    <div className="text-xs font-mono font-bold text-[#001428]">
                      {score?.overall_score != null ? scoreOutOfTen(score.overall_score) : "—"}
                    </div>
                  </div>
                </div>

              </div>

              {/* Scorecard Dimensions (5 cols) */}
              <div className="lg:col-span-5 bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
                <div className="flex items-center justify-between pb-3 border-b border-[#f1f5f9] mb-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={16} className="text-[#0f2942]" />
                    <h2 className="font-bold text-sm text-[#001428]">Scorecard Dimensions</h2>
                  </div>
                  <span className="font-mono text-xs font-bold text-[#001428] bg-[#f8fafc] px-2 py-0.5 border border-[#e2e8f0] rounded-[2px]">
                    {score?.overall_score != null ? scoreOutOfTen(score.overall_score) : "Unrated"}
                  </span>
                </div>

                {score?.overall_score != null ? (
                  <div className="space-y-3.5">
                    {scoreBreakdown.map((item) => {
                      const val = score?.dimensions?.[item.key] ?? score?.breakdown?.[item.key];
                      const hasVal = val !== undefined && val !== null;
                      return (
                        <div key={item.key} className="space-y-1">
                          <div className="flex justify-between text-xs">
                            <span className="text-[#334155] font-medium">{item.label}</span>
                            <span className="font-mono text-[#001428]">
                              {hasVal ? `${Math.round(val)}/100` : "—"}
                            </span>
                          </div>
                          <div className="w-full bg-[#f1f5f9] h-1.5 rounded-full overflow-hidden">
                            <div 
                              className="bg-[#0f2942] h-full rounded-full transition-all duration-500"
                              style={{ width: hasVal ? `${Math.min(100, Math.max(0, val))}%` : "0%" }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="py-8 text-center text-xs text-[#64748b] space-y-2">
                    <ShieldCheck size={28} className="mx-auto text-[#cbd5e1]" />
                    <div className="font-medium text-[#001428]">Insufficient Data for Scoring</div>
                    <p className="text-[11px] text-[#64748b] leading-relaxed max-w-xs mx-auto">
                      Quantitative scoring requires multi-year audited financial statements and DRHP risk factor extraction.
                    </p>
                  </div>
                )}

                {score?.summary && (
                  <div className="mt-5 p-3 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px] text-xs text-[#475569] leading-relaxed">
                    <span className="font-bold text-[#001428]">Analyst Thesis: </span>
                    {score.summary}
                  </div>
                )}
              </div>

            </div>

            {/* Third Row: Top Risk Factors Preview */}
            {risks.length > 0 && (
              <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
                <div className="flex items-center justify-between pb-3 border-b border-[#f1f5f9] mb-4">
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={16} className="text-[#b45309]" />
                    <h2 className="font-bold text-sm text-[#001428]">Key Prospectus Risk Factors</h2>
                  </div>
                  <button 
                    onClick={() => setActiveTab("Risks")}
                    className="text-xs text-[#0f2942] font-semibold hover:underline inline-flex items-center gap-1"
                  >
                    <span>View all {risks.length} factors</span>
                    <ArrowUpRight size={13} />
                  </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {risks.slice(0, 2).map((r: Any, idx: number) => (
                    <div key={r.id || idx} className="p-3.5 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                      <div className="flex items-center justify-between mb-1.5">
                        <span className="font-mono text-[10px] font-bold text-[#b45309] bg-[#fefce8] px-2 py-0.5 border border-[#fde68a] rounded-[2px]">
                          {r.severity} Severity
                        </span>
                        {r.source_page != null && (
                          <span className="font-mono text-[10px] text-[#64748b]">Page {r.source_page}</span>
                        )}
                      </div>
                      <h3 className="font-bold text-xs text-[#001428] mb-1">{r.category}</h3>
                      <p className="text-xs text-[#475569] leading-relaxed line-clamp-2">{r.summary}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Company Profile Details */}
            <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
              <h2 className="font-bold text-sm text-[#001428] mb-2">Company Profile &amp; Business Overview</h2>
              <p className="text-xs text-[#475569] leading-relaxed">
                {ipo.description || "Comprehensive corporate issuer profile and statutory prospectus notes are currently indexing."}
              </p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mt-4 pt-3 border-t border-[#f1f5f9] text-xs">
                <div>
                  <span className="text-[#64748b]">Industry Sector:</span>
                  <div className="font-medium text-[#001428] mt-0.5">{ipo.sector || "—"}</div>
                </div>
                <div>
                  <span className="text-[#64748b]">Exchange:</span>
                  <div className="font-medium text-[#001428] mt-0.5">{ipo.exchange || "NSE / BSE"}</div>
                </div>
                <div>
                  <span className="text-[#64748b]">Listing Segment:</span>
                  <div className="font-medium text-[#001428] mt-0.5">{ipo.listing_segment || "Mainboard"}</div>
                </div>
                <div>
                  <span className="text-[#64748b]">Data Source:</span>
                  <div className="font-medium text-[#001428] mt-0.5 font-mono">{ipo.data_source || "live"}</div>
                </div>
              </div>
            </div>

          </div>
        )}

        {/* TAB 2: FINANCIALS */}
        {activeTab === "Financials" && (
          <div className="space-y-5">
            <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
              <div className="flex items-center justify-between pb-3 border-b border-[#f1f5f9] mb-4">
                <div>
                  <h2 className="font-bold text-base text-[#001428]">Audited Historical Financial Trajectory</h2>
                  <p className="text-xs text-[#64748b]">Consolidated financial statements reported under Ind AS (in ₹ Crores)</p>
                </div>
                <span className="font-mono text-xs text-[#0f2942] bg-[#f8fafc] px-2.5 py-1 border border-[#e2e8f0] rounded-[2px] font-semibold">
                  AUDITED STATEMENTS
                </span>
              </div>

              {finItems.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#e2e8f0] bg-[#f8fafc] text-[#475569]">
                        <th className="py-2.5 px-3 font-semibold">FISCAL PERIOD</th>
                        <th className="py-2.5 px-3 font-semibold">PERIOD TYPE</th>
                        <th className="py-2.5 px-3 font-semibold text-right">REVENUE</th>
                        <th className="py-2.5 px-3 font-semibold text-right">EBITDA</th>
                        <th className="py-2.5 px-3 font-semibold text-right">EBIT</th>
                        <th className="py-2.5 px-3 font-semibold text-right">PAT (NET PROFIT)</th>
                        <th className="py-2.5 px-3 font-semibold text-right">EBITDA MARGIN</th>
                        <th className="py-2.5 px-3 font-semibold text-right">PAT MARGIN</th>
                        <th className="py-2.5 px-3 font-semibold text-right">ROE (%)</th>
                        <th className="py-2.5 px-3 font-semibold text-right">ROCE (%)</th>
                        <th className="py-2.5 px-3 font-semibold text-right">NET DEBT</th>
                        <th className="py-2.5 px-3 font-semibold text-right">YOY GROWTH</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#f1f5f9]">
                      {finItems.map((fi: Any, idx: number) => (
                        <tr key={fi.id || fi.fiscal_year || idx} className="hover:bg-[#f8fafc] transition-colors">
                          <td className="py-2.5 px-3 font-mono font-bold text-[#001428]">{fi.fiscal_year}</td>
                          <td className="py-2.5 px-3 text-[#64748b]">{fi.period_type || "Annual"}</td>
                          <td className="py-2.5 px-3 font-mono text-right font-medium text-[#001428]">{n(fi.revenue)}</td>
                          <td className={`py-2.5 px-3 font-mono text-right font-medium ${fi.ebitda < 0 ? "text-[#b91c1c]" : "text-[#001428]"}`}>
                            {n(fi.ebitda)}
                          </td>
                          <td className={`py-2.5 px-3 font-mono text-right ${fi.ebit < 0 ? "text-[#b91c1c]" : "text-[#475569]"}`}>
                            {n(fi.ebit)}
                          </td>
                          <td className={`py-2.5 px-3 font-mono text-right font-medium ${fi.pat < 0 ? "text-[#b91c1c]" : "text-[#001428]"}`}>
                            {n(fi.pat)}
                          </td>
                          <td className={`py-2.5 px-3 font-mono text-right ${fi.ebitda_margin < 0 ? "text-[#b91c1c]" : "text-[#15803d]"}`}>
                            {n(fi.ebitda_margin, "%", 1)}
                          </td>
                          <td className={`py-2.5 px-3 font-mono text-right ${fi.pat_margin < 0 ? "text-[#b91c1c]" : "text-[#15803d]"}`}>
                            {n(fi.pat_margin, "%", 1)}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#001428]">
                            {fi.roe != null ? `${fi.roe.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#001428]">
                            {fi.roce != null ? `${fi.roce.toFixed(1)}%` : "—"}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#475569]">{n(fi.net_debt)}</td>
                          <td className="py-2.5 px-3 font-mono text-right font-semibold text-[#001428]">
                            {(fi.yoy_revenue_growth ?? fi.yoy_growth) != null ? `${(fi.yoy_revenue_growth ?? fi.yoy_growth).toFixed(1)}%` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="py-12 text-center text-xs text-[#64748b] space-y-1.5">
                  <div className="font-semibold text-[#001428] text-sm">Audited Financial Statements Pending Extraction</div>
                  <p className="max-w-md mx-auto text-[#64748b]">
                    Detailed historical balance sheets and profit & loss statements are pending statutory filing extraction for this issuer.
                  </p>
                </div>
              )}

              {/* Financial Chart Component */}
              {financials && finItems.length > 0 && (
                <div className="mt-6 pt-5 border-t border-[#f1f5f9]">
                  <h3 className="font-bold text-xs text-[#001428] mb-3">Revenue &amp; Margin Expansion Visual Trajectory</h3>
                  <FinancialChart items={financials?.items || []} />
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: VALUATION */}
        {activeTab === "Valuation" && (
          <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm space-y-6">
            <div className="flex items-center justify-between pb-3 border-b border-[#f1f5f9]">
              <div>
                <h2 className="font-bold text-base text-[#001428]">Valuation Framework &amp; Multiple Analysis</h2>
                <p className="text-xs text-[#64748b]">Fundamental multiples benchmarked against issue price band and market capitalization</p>
              </div>
              <span className="font-mono text-xs text-[#0f2942] bg-[#f8fafc] px-2.5 py-1 border border-[#e2e8f0] rounded-[2px] font-semibold">
                {valuation?.CURRENT_MARKET ? "CURRENT MARKET" : (valuation?.IPO_AT_ISSUE ? "AT ISSUE" : "VALUATION")}
              </span>
            </div>

            {currentValuation ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <div className="p-4 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Market Cap</div>
                    <div className="text-xl font-bold text-[#001428] font-mono">
                      {currentValuation.market_cap ? `₹${n(Math.round(currentValuation.market_cap))} Cr` : "—"}
                    </div>
                  </div>
                  <div className="p-4 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Enterprise Value</div>
                    <div className="text-xl font-bold text-[#001428] font-mono">
                      {currentValuation.enterprise_value ? `₹${n(Math.round(currentValuation.enterprise_value))} Cr` : "—"}
                    </div>
                  </div>
                  <div className="p-4 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">EV / Sales</div>
                    <div className="text-xl font-bold text-[#001428] font-mono">
                      {currentValuation.ev_sales ? `${currentValuation.ev_sales.toFixed(2)}x` : "—"}
                    </div>
                  </div>
                  <div className="p-4 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="text-[10px] font-bold text-[#64748b] uppercase tracking-wider mb-1">Price / Sales (P/S)</div>
                    <div className="text-xl font-bold text-[#001428] font-mono">
                      {currentValuation.ps ? `${currentValuation.ps.toFixed(2)}x` : "—"}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px] space-y-3">
                    <h3 className="font-bold text-xs text-[#001428] uppercase tracking-wider">Earnings Multiples</h3>
                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between py-1.5 border-b border-[#e2e8f0]">
                        <span className="text-[#475569]">Price to Earnings (P/E)</span>
                        <span className="font-mono font-semibold text-[#001428]">
                          {currentValuation.pe ? `${currentValuation.pe.toFixed(2)}x` : "—"}
                        </span>
                      </div>
                      <div className="flex justify-between py-1.5">
                        <span className="text-[#475569]">EV / EBITDA Multiple</span>
                        <span className="font-mono font-semibold text-[#001428]">
                          {currentValuation.ev_ebitda ? `${currentValuation.ev_ebitda.toFixed(2)}x` : "—"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="p-4 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <h3 className="font-bold text-xs text-[#001428] uppercase tracking-wider mb-2">Institutional Methodology Note</h3>
                    <p className="text-xs text-[#475569] leading-relaxed">
                      The valuation framework benchmarks multiples against listed domestic peers to analyze premium or discount pricing. Valuation figures reflect audited annual results and capital structures.
                    </p>
                  </div>
                </div>
              </>
            ) : (
              <div className="py-12 text-center text-xs text-[#64748b] space-y-1.5">
                <div className="font-semibold text-[#001428] text-sm">Valuation Multiples Pending Statements</div>
                <p className="max-w-md mx-auto text-[#64748b]">
                  Fundamental and implied valuation multiples will be calculated upon filing of statutory financial statements and price band determination.
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 4: PEERS */}
        {activeTab === "Peers" && (
          <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-[#f1f5f9] mb-4 gap-2">
              <div>
                <h2 className="font-bold text-base text-[#001428]">Peer Valuation &amp; Multiple Comparison</h2>
                <p className="text-xs text-[#64748b]">Comparative multiples benchmarked against listed domestic industry peers</p>
              </div>
              <span className="font-mono text-xs text-[#0f2942] bg-[#f8fafc] px-2.5 py-1 border border-[#e2e8f0] rounded-[2px] font-semibold self-start sm:self-auto">
                SECTOR: {ipo.sector?.toUpperCase() || "EQUITY"}
              </span>
            </div>

            {peersData?.peers && peersData.peers.length > 0 ? (
              <div className="space-y-4">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs border-collapse">
                    <thead>
                      <tr className="border-b border-[#e2e8f0] bg-[#f8fafc] text-[#475569]">
                        <th className="py-2.5 px-3 font-semibold">Company</th>
                        <th className="py-2.5 px-3 font-semibold">Context</th>
                        <th className="py-2.5 px-3 font-semibold text-right">Mkt Cap (₹ Cr)</th>
                        <th className="py-2.5 px-3 font-semibold text-right">P/E</th>
                        <th className="py-2.5 px-3 font-semibold text-right">P/S</th>
                        <th className="py-2.5 px-3 font-semibold text-right">EV/EBITDA</th>
                        <th className="py-2.5 px-3 font-semibold text-right">EV/Sales</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#f1f5f9]">
                      {/* Target Company Rows */}
                      {peersData.target?.current_market ? (
                        <tr className="bg-[#f0f9ff] border-b border-[#cbd5e1]">
                          <td className="py-2.5 px-3 font-bold text-[#0f2942]">
                            <div className="flex items-center gap-1.5">
                              <span>{peersData.target?.name || ipo.name}</span>
                              <span className="text-[10px] bg-[#0f2942] text-white px-1.5 py-0.5 rounded-[2px] font-mono">TARGET</span>
                            </div>
                          </td>
                          <td className="py-2 px-3 text-[#0369a1] font-mono text-[11px]">Current Market</td>
                          <td className="py-2 px-3 font-mono text-right text-[#001428]">
                            {peersData.target.current_market.market_cap ? n(Math.round(peersData.target.current_market.market_cap)) : "—"}
                          </td>
                          <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target.current_market.pe)}</td>
                          <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target.current_market.ps)}</td>
                          <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target.current_market.ev_ebitda)}</td>
                          <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target.current_market.ev_sales)}</td>
                        </tr>
                      ) : (
                        <>
                          <tr className="bg-[#f0f9ff]">
                            <td className="py-2.5 px-3 font-bold text-[#0f2942]" rowSpan={2}>
                              <div className="flex items-center gap-1.5">
                                <span>{peersData.target?.name || ipo.name}</span>
                                <span className="text-[10px] bg-[#0f2942] text-white px-1.5 py-0.5 rounded-[2px] font-mono">TARGET</span>
                              </div>
                            </td>
                            <td className="py-2 px-3 text-[#0369a1] font-mono text-[11px]">Lower Band (IPO)</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">
                              {peersData.target?.lower_band?.implied_market_cap ? n(Math.round(peersData.target.lower_band.implied_market_cap)) : "—"}
                            </td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.lower_band?.pe)}</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.lower_band?.ps)}</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.lower_band?.ev_ebitda)}</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.lower_band?.ev_sales)}</td>
                          </tr>
                          <tr className="bg-[#f0f9ff] border-b border-[#cbd5e1]">
                            <td className="py-2 px-3 text-[#0369a1] font-mono text-[11px]">Upper Band (IPO)</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">
                              {peersData.target?.upper_band?.implied_market_cap ? n(Math.round(peersData.target.upper_band.implied_market_cap)) : "—"}
                            </td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.upper_band?.pe)}</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.upper_band?.ps)}</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.upper_band?.ev_ebitda)}</td>
                            <td className="py-2 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.target?.upper_band?.ev_sales)}</td>
                          </tr>
                        </>
                      )}

                      {/* Peer Rows */}
                      {peersData.peers.map((peer: Any, idx: number) => (
                        <tr key={idx} className="hover:bg-[#f8fafc] transition-colors">
                          <td className="py-2.5 px-3 font-medium text-[#001428]">{peer.name}</td>
                          <td className="py-2.5 px-3 text-[#64748b] text-[11px]">Market ({peer.valuation_date || "Current"})</td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#475569]">
                            {peer.market_cap ? n(Math.round(peer.market_cap)) : "—"}
                          </td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peer.pe)}</td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peer.ps)}</td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peer.ev_ebitda)}</td>
                          <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peer.ev_sales)}</td>
                        </tr>
                      ))}

                      {/* Median Row */}
                      <tr className="bg-[#f8fafc] font-semibold border-t border-[#e2e8f0]">
                        <td className="py-2.5 px-3 text-[#475569] italic">Peer Median</td>
                        <td className="py-2.5 px-3 text-[#64748b] text-[11px] font-mono">n={peersData.peer_statistics?.pe?.observations ?? peersData.peers.length}</td>
                        <td className="py-2.5 px-3 font-mono text-right text-[#64748b]">—</td>
                        <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.peer_statistics?.pe?.median)}</td>
                        <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.peer_statistics?.ps?.median)}</td>
                        <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.peer_statistics?.ev_ebitda?.median)}</td>
                        <td className="py-2.5 px-3 font-mono text-right text-[#001428]">{formatMultiple(peersData.peer_statistics?.ev_sales?.median)}</td>
                      </tr>

                      {/* Premium / Discount Rows */}
                      {peersData.comparison?.current_market ? (
                        <tr className="border-t border-[#cbd5e1] bg-[#fafafa]">
                          <td className="py-2.5 px-3 text-[#64748b] font-medium">Premium / (Discount) vs Median</td>
                          <td className="py-2 px-3 text-[#64748b] text-[11px]">Current Market</td>
                          <td className="py-2 px-3 font-mono text-right text-[#64748b]">—</td>
                          <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison.current_market.pe)}</td>
                          <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison.current_market.ps)}</td>
                          <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison.current_market.ev_ebitda)}</td>
                          <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison.current_market.ev_sales)}</td>
                        </tr>
                      ) : (
                        <>
                          <tr className="border-t border-[#cbd5e1] bg-[#fafafa]">
                            <td className="py-2.5 px-3 text-[#64748b] font-medium" rowSpan={2}>Premium / (Discount) vs Median</td>
                            <td className="py-2 px-3 text-[#64748b] text-[11px]">Lower Band</td>
                            <td className="py-2 px-3 font-mono text-right text-[#64748b]">—</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.lower_band?.pe)}</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.lower_band?.ps)}</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.lower_band?.ev_ebitda)}</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.lower_band?.ev_sales)}</td>
                          </tr>
                          <tr className="bg-[#fafafa]">
                            <td className="py-2 px-3 text-[#64748b] text-[11px]">Upper Band</td>
                            <td className="py-2 px-3 font-mono text-right text-[#64748b]">—</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.upper_band?.pe)}</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.upper_band?.ps)}</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.upper_band?.ev_ebitda)}</td>
                            <td className="py-2 px-3 font-mono text-right">{formatPremium(peersData.comparison?.upper_band?.ev_sales)}</td>
                          </tr>
                        </>
                      )}
                    </tbody>
                  </table>
                </div>

                <div className="p-3 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px] text-xs text-[#64748b] flex items-start gap-2">
                  <Info size={14} className="shrink-0 mt-0.5 text-[#0f2942]" />
                  <span>
                    Target valuation benchmarks active market quotations or IPO-at-issue price bands against listed domestic peers. A negative premium indicates the target is priced at a discount to the peer median.
                  </span>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-[#64748b] space-y-2">
                <Users size={32} className="mx-auto text-[#cbd5e1]" />
                <div className="font-semibold text-[#001428] text-sm">No Listed Domestic Peers Benchmarked</div>
                <p className="max-w-md mx-auto text-[#64748b]">
                  No comparable listed peers are currently cataloged in the {ipo.sector || "equity"} sector within the institutional coverage universe.
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB 5: RISKS */}
        {activeTab === "Risks" && (
          <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
            <div className="flex items-center justify-between pb-3 border-b border-[#f1f5f9] mb-4">
              <div>
                <h2 className="font-bold text-base text-[#001428]">Key Red Herring Risk Factors (DRHP Disclosures)</h2>
                <p className="text-xs text-[#64748b]">Extracted directly from statutory filing prospectuses and auditor notes</p>
              </div>
              <span className="font-mono text-xs text-[#b45309] bg-[#fefce8] px-2.5 py-1 border border-[#fde68a] rounded-[2px] font-semibold">
                {risks.length} FACTORS AUDITED
              </span>
            </div>

            {risks.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {risks.map((r: Any, idx: number) => (
                  <div key={r.id || idx} className="p-4 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-[10px] font-bold text-[#b45309] bg-[#fefce8] px-2 py-0.5 border border-[#fde68a] rounded-[2px]">
                        {r.severity} Severity
                      </span>
                      {r.source_page != null && (
                        <span className="font-mono text-[10px] text-[#64748b] flex items-center gap-1">
                          <FileText size={12} /> Prospectus Page {r.source_page}
                        </span>
                      )}
                    </div>
                    <h3 className="font-bold text-xs text-[#001428] mb-1.5">{r.category}</h3>
                    <p className="text-xs text-[#475569] leading-relaxed">{r.summary}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-[#64748b]">
                No specific risk factors cataloged for this issue yet.
              </div>
            )}
          </div>
        )}

        {/* TAB 6: DCF */}
        {activeTab === "DCF" && (
          <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between pb-3 border-b border-[#f1f5f9] gap-2">
              <div>
                <h2 className="font-bold text-base text-[#001428]">Discounted Cash Flow (DCF) Valuation Model</h2>
                <p className="text-xs text-[#64748b]">Interactive multi-stage projection model calibrated against audited base metrics</p>
              </div>
              <span className="font-mono text-xs text-[#0f2942] bg-[#f8fafc] px-2.5 py-1 border border-[#e2e8f0] rounded-[2px] font-semibold self-start sm:self-auto">
                BASE REV: {dcfResult?.inputs?.historical?.base_revenue ? `₹${n(dcfResult.inputs.historical.base_revenue)} Cr` : "AUDITED"}
              </span>
            </div>

            {finItems.length === 0 ? (
              <div className="py-12 text-center text-xs text-[#64748b] space-y-2">
                <Calculator size={32} className="mx-auto text-[#cbd5e1]" />
                <div className="font-semibold text-[#001428] text-sm">DCF Valuation Pending Annual Financial Statements</div>
                <p className="max-w-md mx-auto text-[#64748b]">
                  A source-backed annual financial period is required to calibrate baseline revenues, margins, and free cash flows for discounted cash flow modeling.
                </p>
              </div>
            ) : (
              <>
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                  {/* Controls Column (5 cols) */}
                  <div className="lg:col-span-5 space-y-4 bg-[#f8fafc] p-4 border border-[#e2e8f0] rounded-[2px]">
                    <h3 className="font-bold text-xs uppercase tracking-wider text-[#0f2942]">Model Assumptions &amp; Inputs</h3>

                    {/* EBITDA Margin */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-[#334155]">EBITDA Margin</span>
                        <span className="font-mono font-semibold text-[#001428]">{dcfMargin.toFixed(1)}%</span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="60"
                        step="0.5"
                        value={dcfMargin}
                        onChange={e => setDcfMargin(Number(e.target.value))}
                        className="w-full accent-[#0f2942] h-1.5 bg-[#e2e8f0] rounded-lg appearance-none cursor-pointer"
                      />
                    </div>

                    {/* Revenue Growth */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-[#334155]">Revenue Growth (CAGR)</span>
                        <span className="font-mono font-semibold text-[#001428]">{dcfGrowth.toFixed(1)}%</span>
                      </div>
                      <input
                        type="range"
                        min="-10"
                        max="60"
                        step="1"
                        value={dcfGrowth}
                        onChange={e => setDcfGrowth(Number(e.target.value))}
                        className="w-full accent-[#0f2942] h-1.5 bg-[#e2e8f0] rounded-lg appearance-none cursor-pointer"
                      />
                    </div>

                    {/* Discount Rate (WACC) */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-[#334155]">Discount Rate (WACC)</span>
                        <span className="font-mono font-semibold text-[#001428]">{dcfDiscount.toFixed(1)}%</span>
                      </div>
                      <input
                        type="range"
                        min="6"
                        max="25"
                        step="0.5"
                        value={dcfDiscount}
                        onChange={e => setDcfDiscount(Number(e.target.value))}
                        className="w-full accent-[#0f2942] h-1.5 bg-[#e2e8f0] rounded-lg appearance-none cursor-pointer"
                      />
                    </div>

                    {/* Terminal Growth */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between text-xs font-medium">
                        <span className="text-[#334155]">Terminal Growth Rate</span>
                        <span className="font-mono font-semibold text-[#001428]">{dcfTerminal.toFixed(1)}%</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max={Math.max(2, dcfDiscount - 1)}
                        step="0.5"
                        value={dcfTerminal}
                        onChange={e => setDcfTerminal(Number(e.target.value))}
                        className="w-full accent-[#0f2942] h-1.5 bg-[#e2e8f0] rounded-lg appearance-none cursor-pointer"
                      />
                    </div>

                    <div className="pt-2 border-t border-[#e2e8f0] space-y-3">
                      <div className="text-[11px] font-bold text-[#64748b] uppercase tracking-wider">Secondary Variables</div>

                      {/* Tax Rate */}
                      <div className="flex justify-between text-xs">
                        <span className="text-[#475569]">Effective Tax Rate</span>
                        <span className="font-mono text-[#001428]">{dcfTax}%</span>
                      </div>

                      {/* D&A */}
                      <div className="flex justify-between text-xs">
                        <span className="text-[#475569]">D&amp;A (% of Rev)</span>
                        <span className="font-mono text-[#001428]">{dcfDaPct}%</span>
                      </div>

                      {/* CapEx */}
                      <div className="flex justify-between text-xs">
                        <span className="text-[#475569]">CapEx (% of Rev)</span>
                        <span className="font-mono text-[#001428]">{dcfCapexPct}%</span>
                      </div>

                      {/* Change in NWC */}
                      <div className="flex justify-between text-xs">
                        <span className="text-[#475569]">Working Capital (% of Rev)</span>
                        <span className="font-mono text-[#001428]">{dcfNwcPct}%</span>
                      </div>
                    </div>
                  </div>

                  {/* Output Column (7 cols) */}
                  <div className="lg:col-span-7 space-y-4">
                    {/* Valuation Summary Card */}
                    <div className="p-5 bg-[#f8fafc] border border-[#e2e8f0] rounded-[2px]">
                      <div className="text-[11px] font-bold uppercase tracking-wider text-[#64748b] mb-1">
                        Implied Enterprise Value
                      </div>
                      {dcfError ? (
                        <div className="text-xs text-[#b91c1c] font-medium">{dcfError}</div>
                      ) : (
                        <div>
                          <div className="text-3xl font-extrabold text-[#001428] font-mono tracking-tight">
                            ₹{dcfResult?.valuation?.enterprise_value ? n(Math.round(dcfResult.valuation.enterprise_value)) : "—"}
                            <span className="text-sm font-semibold text-[#64748b] ml-1.5 font-sans">Cr</span>
                          </div>
                          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[#475569]">
                            <span>Terminal Value PV: <b className="font-mono text-[#001428]">₹{dcfResult?.valuation?.terminal_value_pv ? n(Math.round(dcfResult.valuation.terminal_value_pv)) : "—"} Cr</b></span>
                            {dcfResult?.valuation?.intrinsic_value_per_share != null && (
                              <span>Intrinsic Value / Share: <b className="font-mono text-[#0f2942]">₹{n(Math.round(dcfResult.valuation.intrinsic_value_per_share))}</b></span>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Projections Chart */}
                    <div className="p-4 bg-white border border-[#e2e8f0] rounded-[2px]">
                      <div className="text-xs font-semibold text-[#001428] mb-3">5-Year Projected FCFF vs Present Value (₹ Cr)</div>
                      <div className="h-44 w-full">
                        {dcfChartData.length > 0 ? (
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={dcfChartData} margin={{ top: 5, right: 10, bottom: 0, left: 0 }}>
                              <CartesianGrid strokeDasharray="2 2" stroke="#f1f5f9" vertical={false} />
                              <XAxis dataKey="name" tick={{ fill: "#64748b", fontSize: 11 }} axisLine={{ stroke: "#e2e8f0" }} tickLine={false} />
                              <YAxis tick={{ fill: "#64748b", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `₹${v}`} width={55} />
                              <Tooltip
                                contentStyle={{ background: "#ffffff", border: "1px solid #e2e8f0", borderRadius: 2, fontSize: 11, color: "#0f172a" }}
                                formatter={(value: any) => [`₹${Number(value).toFixed(0)} Cr`, undefined]}
                              />
                              <Bar dataKey="fcff" name="Free Cash Flow" fill="#94a3b8" radius={[2, 2, 0, 0]} />
                              <Bar dataKey="present_value" name="Present Value" fill="#0f2942" radius={[2, 2, 0, 0]} />
                            </BarChart>
                          </ResponsiveContainer>
                        ) : (
                          <div className="h-full flex items-center justify-center text-xs text-[#94a3b8]">
                            Projections will render once baseline financials are loaded.
                          </div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Sensitivity Matrix */}
                {dcfResult?.sensitivity && (
                  <div className="pt-4 border-t border-[#e2e8f0]">
                    <h3 className="font-bold text-xs uppercase tracking-wider text-[#001428] mb-3">
                      Sensitivity Matrix: {dcfResult?.valuation?.intrinsic_value_per_share != null ? "Intrinsic Value / Share (₹)" : "Enterprise Value (₹ Cr)"} across WACC vs Terminal Growth
                    </h3>
                    <div className="overflow-x-auto">
                      <table className="w-full text-center text-xs border-collapse border border-[#e2e8f0]">
                        <thead>
                          <tr className="bg-[#f8fafc] text-[#475569]">
                            <th className="py-2 px-3 border border-[#e2e8f0] text-left font-semibold">WACC \ Term Growth</th>
                            {dcfResult.sensitivity.terminal_growth_values.map((tg: number) => (
                              <th key={tg} className="py-2 px-3 border border-[#e2e8f0] font-semibold font-mono">{tg}%</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {dcfResult.sensitivity.wacc_values.map((w: number, rIdx: number) => (
                            <tr key={w} className="hover:bg-[#f8fafc]">
                              <td className="py-2 px-3 border border-[#e2e8f0] text-left font-semibold font-mono text-[#001428] bg-[#f8fafc]">{w}%</td>
                              {dcfResult.sensitivity.grid[rIdx].map((cell: any, cIdx: number) => (
                                <td key={cIdx} className="py-2 px-3 border border-[#e2e8f0] font-mono text-[#001428]">
                                  {cell != null ? (dcfResult?.valuation?.intrinsic_value_per_share != null ? `₹${Math.round(cell).toLocaleString("en-IN")}` : `₹${n(Math.round(cell))} Cr`) : "—"}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* TAB 7: RESEARCH */}
        {activeTab === "Research" && (
          <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-5 shadow-sm">
            <div className="pb-3 border-b border-[#f1f5f9] mb-4">
              <h2 className="font-bold text-base text-[#001428]">Contextual Equity Research Terminal</h2>
              <p className="text-xs text-[#64748b]">Evidence-first research engine querying financial metrics, filing citations, and valuation multiples</p>
            </div>

            <div className="flex gap-2 mb-4">
              <input 
                className="flex-1 h-9 px-3 bg-[#f8fafc] border border-[#cbd5e1] rounded-[2px] text-xs text-[#0f172a] placeholder-[#94a3b8] focus:outline-none focus:border-[#0f2942] focus:bg-white transition-all font-sans"
                value={question} 
                onChange={e => setQuestion(e.target.value)} 
                onKeyDown={e => e.key === "Enter" && ask()} 
                placeholder="Ask an analytical question regarding valuation, profitability, or risks..."
              />
              <button 
                className="h-9 px-4 inline-flex items-center gap-1.5 bg-[#0f2942] text-white text-xs font-semibold rounded-[2px] hover:bg-[#1e3a8a] transition-colors shrink-0 disabled:opacity-60"
                onClick={ask} 
                disabled={busy}
              >
                {busy ? "Researching…" : <><Send size={13} /><span>Query Agent</span></>}
              </button>
            </div>

            {error && <p className="text-xs text-[#b91c1c] mb-3">{error}</p>}

            {answer && (
              <div className="p-4 bg-[#f8fafc] border border-[#cbd5e1] rounded-[2px]">
                <div className="flex items-center justify-between pb-2 border-b border-[#e2e8f0] mb-3">
                  <span className="font-bold text-xs text-[#0f2942] uppercase tracking-wider">Research Consensus</span>
                  {answer.tool_trace && (
                    <span className="font-mono text-[10px] text-[#64748b]">
                      Tools: {answer.tool_trace.join(" → ")}
                    </span>
                  )}
                </div>
                
                <p className="text-xs text-[#0f172a] leading-relaxed mb-4">{answer.answer}</p>

                {answer.claims && answer.claims.length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-[#e2e8f0]">
                    <span className="font-bold text-[10px] text-[#64748b] uppercase tracking-wider">Filing Citations &amp; Evidence</span>
                    {answer.claims.map((claim: any, index: number) => (
                      <div key={index} className="p-2.5 bg-white border border-[#e2e8f0] rounded-[2px] text-xs">
                        <div className="text-[#0f172a] font-medium mb-1">{claim.text}</div>
                        {claim.citations && claim.citations.map((cite: any, cidx: number) => (
                          <div key={cidx} className="mt-1.5 pl-2.5 border-l-2 border-[#0f2942] text-[11px]">
                            <div className="font-mono text-[10px] text-[#64748b]">
                              Source Document {cite.document_id}, Page {cite.page} {cite.section ? `(${cite.section})` : ""}
                            </div>
                            <div className="italic text-[#475569]">"{cite.excerpt}"</div>
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

        {/* TAB 8: FILINGS */}
        {activeTab === "Filings" && (
          <div className="bg-white border border-[#e2e8f0] rounded-[2px] p-8 shadow-sm text-center">
            <FileText size={36} className="text-[#94a3b8] mx-auto mb-3 opacity-60" />
            <h3 className="font-bold text-sm text-[#001428] mb-1">Statutory Prospectus &amp; SEBI Filings</h3>
            <p className="text-xs text-[#64748b] max-w-md mx-auto mb-4 leading-relaxed">
              Official Draft Red Herring Prospectuses (DRHP), Red Herring Prospectuses (RHP), and Anchor Book Allotments are synced directly from exchanges.
            </p>
            <div className="inline-flex items-center gap-3 text-xs font-mono text-[#475569] bg-[#f8fafc] px-4 py-2 border border-[#e2e8f0] rounded-[2px]">
              <span>Exchange: {ipo.exchange || "NSE / BSE"}</span>
              <span className="text-[#cbd5e1]">|</span>
              <span>Listing Segment: {ipo.listing_segment || "Mainboard"}</span>
              <span className="text-[#cbd5e1]">|</span>
              <span>Source: {ipo.data_source || "live"}</span>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
