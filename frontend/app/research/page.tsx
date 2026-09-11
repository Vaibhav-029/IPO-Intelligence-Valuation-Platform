"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import Link from "next/link";
import { 
  Send, 
  FileText, 
  ShieldCheck, 
  Plus, 
  Trash2, 
  Search, 
  ExternalLink, 
  CheckCircle2, 
  AlertTriangle, 
  Layers, 
  Maximize2, 
  History, 
  Building2, 
  Clock, 
  Sparkles,
  TrendingUp,
  Briefcase,
  SlidersHorizontal,
  ChevronDown
} from "lucide-react";
import { 
  apiFetch, 
  getIPOs, 
  getIPO, 
  getResearchSessions, 
  getResearchSession, 
  createResearchSession, 
  sendResearchMessage, 
  deleteResearchSession, 
  IPO, 
  ResearchSessionItem, 
  ResearchMessageItem, 
  ResearchClaim, 
  ResearchResponse 
} from "../../lib/api";
import { date, priceBand, issueSize, scoreOutOfTen } from "../../lib/format";
import { useAuth } from "../../lib/AuthContext";

type Any = Record<string, any>;

interface LocalSession {
  id: number;
  ipo_id: number;
  title: string;
  created_at: string;
  lastMessage?: string;
}

export default function ResearchWorkspace() {
  const { user, setAuthModalOpen } = useAuth();

  // Core Data
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [selectedIpoId, setSelectedIpoId] = useState<number | null>(null);
  const [selectedIpo, setSelectedIpo] = useState<Any | null>(null);
  const [valuationData, setValuationData] = useState<Any | null>(null);
  const [risksData, setRisksData] = useState<Any[]>([]);
  const [scoreData, setScoreData] = useState<Any | null>(null);

  // Sessions & Dialogue
  const [sessions, setSessions] = useState<LocalSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ResearchMessageItem[]>([]);
  
  // UI & Controls
  const [question, setQuestion] = useState("");
  const [sessionFilter, setSessionFilter] = useState("");
  const [universeFilter, setUniverseFilter] = useState<"ALL" | "MAIN" | "SME" | "DRHP">("ALL");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTabMobile, setActiveTabMobile] = useState<"workstations" | "dialogue" | "evidence">("dialogue");

  // Latency telemetry simulation for institutional terminal feel
  const [latency, setLatency] = useState("18ms");

  const messageEndRef = useRef<HTMLDivElement>(null);

  // 1. Initial Load: Fetch IPO Directory
  useEffect(() => {
    getIPOs("all")
      .then(data => {
        setIpos(data || []);
        if (data && data.length > 0) {
          // Default to Rentomojo or Swiggy or first IPO
          const defaultIpo = data.find(i => i.slug?.toLowerCase().includes("rentomojo")) 
            || data.find(i => i.slug?.toLowerCase().includes("swiggy"))
            || data[0];
          setSelectedIpoId(defaultIpo.id);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load IPO directory:", err);
        setError("Unable to connect to the IPO data feed.");
        setLoading(false);
      });
  }, []);

  // 2. Load User Research Sessions
  const fetchSessions = async () => {
    if (!user) {
      setSessions([]);
      return;
    }
    try {
      const serverSessions = await getResearchSessions();
      if (Array.isArray(serverSessions)) {
        setSessions(serverSessions);
      }
    } catch (e) {
      // Fallback: check localStorage for cached sessions
      try {
        const cached = localStorage.getItem(`ipo_research_sessions_${user.email}`);
        if (cached) {
          setSessions(JSON.parse(cached));
        }
      } catch {}
    }
  };

  useEffect(() => {
    fetchSessions();
  }, [user]);

  // 3. Load Selected IPO Context (Valuation, Risks, Score)
  useEffect(() => {
    if (!selectedIpoId) return;

    const start = performance.now();
    Promise.all([
      getIPO(selectedIpoId).catch(() => null),
      apiFetch(`/ipos/${selectedIpoId}/valuation`).catch(() => null),
      apiFetch(`/ipos/${selectedIpoId}/risks`).catch(() => []),
      apiFetch(`/ipos/${selectedIpoId}/score`).catch(() => null)
    ]).then(([ipoDetail, val, risks, sc]) => {
      setSelectedIpo(ipoDetail);
      setValuationData(val);
      setRisksData(Array.isArray(risks) ? risks : []);
      setScoreData(sc);
      const end = performance.now();
      setLatency(`${Math.max(12, Math.round(end - start))}ms`);
    });
  }, [selectedIpoId]);

  // 4. Load Active Session Messages
  useEffect(() => {
    if (!activeSessionId || !user) {
      setMessages([]);
      return;
    }

    getResearchSession(activeSessionId)
      .then(detail => {
        if (detail && detail.messages) {
          setMessages(detail.messages);
          if (detail.ipo_id && detail.ipo_id !== selectedIpoId) {
            setSelectedIpoId(detail.ipo_id);
          }
        }
      })
      .catch(err => {
        console.error("Failed to load session:", err);
      });
  }, [activeSessionId, user]);

  // Auto-scroll to bottom of messages
  useEffect(() => {
    messageEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Handle New Session
  const handleNewSession = () => {
    setActiveSessionId(null);
    setMessages([]);
    setError(null);
    setQuestion("");
    setActiveTabMobile("dialogue");
  };

  // Switch to an existing session
  const handleSelectSession = (sess: LocalSession) => {
    setActiveSessionId(sess.id);
    setSelectedIpoId(sess.ipo_id);
    setError(null);
    setActiveTabMobile("dialogue");
  };

  // Delete a session
  const handleDeleteSession = async (e: React.MouseEvent, sessId: number) => {
    e.stopPropagation();
    if (!user) return;
    try {
      await deleteResearchSession(sessId);
      setSessions(prev => prev.filter(s => s.id !== sessId));
      if (activeSessionId === sessId) {
        handleNewSession();
      }
    } catch (err: any) {
      console.error("Failed to delete session:", err);
    }
  };

  // Send Question / Run Agent
  const handleAsk = async (customPrompt?: string) => {
    const promptToSend = customPrompt || question;
    if (!promptToSend.trim()) return;

    if (!user) {
      setAuthModalOpen(true);
      return;
    }

    if (!selectedIpoId) {
      setError("Please select a target company to interrogate.");
      return;
    }

    setBusy(true);
    setError(null);

    try {
      let currentSessionId = activeSessionId;

      // Create new session if none is active
      if (!currentSessionId) {
        const title = promptToSend.length > 50 ? `${promptToSend.substring(0, 48)}...` : promptToSend;
        const newSess = await createResearchSession(selectedIpoId, title);
        currentSessionId = newSess.id;
        setActiveSessionId(currentSessionId);
        
        const newLocalSess: LocalSession = {
          id: newSess.id,
          ipo_id: selectedIpoId,
          title: title,
          created_at: newSess.created_at || new Date().toISOString()
        };
        setSessions(prev => [newLocalSess, ...prev.filter(s => s.id !== newSess.id)]);
      }

      // Optimistically append user message
      const userMsg: ResearchMessageItem = {
        role: "user",
        content: promptToSend,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, userMsg]);
      setQuestion("");

      // Execute research message through agent
      const start = performance.now();
      const result: ResearchResponse = await sendResearchMessage(currentSessionId, promptToSend);
      const end = performance.now();
      setLatency(`${Math.round(end - start)}ms`);

      // Append assistant message
      const assistantMsg: ResearchMessageItem = {
        role: "assistant",
        content: result.answer,
        tool_trace: result.tool_trace,
        citations: result.claims,
        created_at: new Date().toISOString()
      };
      setMessages(prev => [...prev, assistantMsg]);

      // Refresh session list to reflect latest timestamps
      fetchSessions();
    } catch (err: any) {
      setError(err.message || "An error occurred while compiling research.");
    } finally {
      setBusy(false);
    }
  };

  // Extract all citations from the active conversation (prioritizing latest assistant message)
  const activeCitations = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      const msg = messages[i];
      if (msg.role === "assistant" && msg.citations && msg.citations.length > 0) {
        const collected: { docId: number; page?: number; section?: string; excerpt: string; claimText: string }[] = [];
        msg.citations.forEach(claim => {
          if (claim.citations) {
            claim.citations.forEach(cite => {
              collected.push({
                docId: cite.document_id,
                page: cite.page,
                section: cite.section,
                excerpt: cite.excerpt,
                claimText: claim.text
              });
            });
          }
        });
        if (collected.length > 0) return collected;
      }
    }
    return [];
  }, [messages]);

  // Filtered Sessions List
  const filteredSessions = useMemo(() => {
    return sessions.filter(s => {
      const targetIpo = ipos.find(i => i.id === s.ipo_id);
      const matchesSearch = !sessionFilter || 
        s.title.toLowerCase().includes(sessionFilter.toLowerCase()) || 
        (targetIpo?.name && targetIpo.name.toLowerCase().includes(sessionFilter.toLowerCase()));
      
      if (!matchesSearch) return false;

      if (universeFilter === "MAIN") return targetIpo?.listing_segment === "Mainboard";
      if (universeFilter === "SME") return targetIpo?.listing_segment === "SME";
      if (universeFilter === "DRHP") return targetIpo?.status === "Upcoming";
      return true;
    });
  }, [sessions, sessionFilter, universeFilter, ipos]);

  // Suggested Institutional Queries
  const promptSuggestions = [
    "Synthesize revenue growth trajectory and EBITDA margin expansion",
    "Summarize top 5 risk factors and legal proceedings disclosed in the DRHP",
    "Compare valuation multiples (P/E, P/S) against listed sector peers",
    "Analyze working capital requirements, total debt, and use of proceeds"
  ];

  // Helper for company initials fallback
  function getInitials(name: string): string {
    if (!name) return "—";
    const words = name.trim().split(/\s+/);
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
  }

  // Format ticker/code for header
  const tickerCode = useMemo(() => {
    if (!selectedIpo) return "NSE/BSE";
    const symbol = selectedIpo.slug ? selectedIpo.slug.toUpperCase().replace(/-/g, "") : "EQUITY";
    const ex = selectedIpo.exchange || (selectedIpo.listing_segment === "SME" ? "BSE SME" : "NSE");
    return `${ex}: ${symbol.substring(0, 10)}`;
  }, [selectedIpo]);

  return (
    <div className="min-h-screen bg-[#f8fafc] text-[#0f172a] pt-14 flex flex-col font-sans">
      
      {/* ── Top Level Institutional Metadata Ribbon ─────────────────────────── */}
      <div className="w-full bg-white border-b border-[#e2e8f0] px-4 py-2 sticky top-14 z-30 shadow-none">
        <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-bold text-[10px] uppercase tracking-wider text-[#64748b]">Terminal / Equities / ECM</span>
            <span className="text-[#cbd5e1]">/</span>
            <div className="inline-flex items-center gap-1.5 font-mono font-semibold text-[#001428] bg-[#f1f5f9] px-2 py-0.5 rounded border border-[#e2e8f0]">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 animate-pulse" />
              {tickerCode}
            </div>
            <span className="text-[#cbd5e1]">/</span>
            <span className="text-[#475569] font-medium hidden sm:inline">RHP Analysis & Valuation Intelligence</span>
          </div>

          <div className="flex items-center gap-3 font-mono text-[11px] text-[#475569]">
            <span className="hidden md:inline">SYNC: <span className="text-[#001428] font-semibold">BSE/NSE FEEDS OK</span></span>
            <span className="text-[#cbd5e1] hidden md:inline">|</span>
            <span>LATENCY: <span className="font-semibold text-[#001428]">{latency}</span></span>
            <span className="text-[#cbd5e1]">|</span>
            <span className="px-2 py-0.5 rounded bg-[#f8fafc] border border-[#e2e8f0] text-[#0f172a] font-medium flex items-center gap-1">
              <CheckCircle2 size={11} className="text-emerald-600" />
              <span>Autosaved</span>
            </span>
          </div>
        </div>
      </div>

      {/* ── Responsive Mobile/Tablet Segmented Switcher (Visible < 1024px) ───── */}
      <div className="lg:hidden bg-white border-b border-[#e2e8f0] px-4 py-2 flex items-center justify-center gap-2">
        <button 
          onClick={() => setActiveTabMobile("workstations")}
          className={`px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-colors ${
            activeTabMobile === "workstations" ? "bg-[#0f2942] text-white" : "bg-[#f8fafc] text-[#475569] border border-[#e2e8f0]"
          }`}
        >
          <Briefcase size={13} />
          <span>Workstations ({sessions.length})</span>
        </button>
        <button 
          onClick={() => setActiveTabMobile("dialogue")}
          className={`px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-colors ${
            activeTabMobile === "dialogue" ? "bg-[#0f2942] text-white" : "bg-[#f8fafc] text-[#475569] border border-[#e2e8f0]"
          }`}
        >
          <Sparkles size={13} />
          <span>Dialogue</span>
        </button>
        <button 
          onClick={() => setActiveTabMobile("evidence")}
          className={`px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1.5 transition-colors ${
            activeTabMobile === "evidence" ? "bg-[#0f2942] text-white" : "bg-[#f8fafc] text-[#475569] border border-[#e2e8f0]"
          }`}
        >
          <ShieldCheck size={13} />
          <span>Evidence ({activeCitations.length})</span>
        </button>
      </div>

      {/* ── Main 3-Column Institutional Workbench Grid ────────────────────── */}
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 py-4 sm:py-6">
        <div className="grid grid-cols-1 lg:grid-cols-12 border border-[#e2e8f0] rounded bg-white overflow-hidden shadow-sm min-h-[calc(100vh-12rem)]">
          
          {/* ════════ COLUMN 1: Coverage & Drafts Rail (3 cols) ════════ */}
          <aside className={`lg:col-span-3 bg-white border-r border-[#e2e8f0] flex flex-col justify-between ${
            activeTabMobile !== "workstations" ? "hidden lg:flex" : "flex"
          }`}>
            <div className="flex flex-col h-full">
              
              {/* Rail Header */}
              <div className="p-3.5 border-b border-[#e2e8f0] flex items-center justify-between bg-white">
                <div>
                  <h2 className="font-serif font-bold text-sm text-[#001428]">Coverage & Drafts</h2>
                  <p className="font-mono text-[10px] text-[#64748b] mt-0.5 uppercase tracking-wider">
                    {sessions.length} ACTIVE WORKSTATIONS
                  </p>
                </div>
                <button 
                  onClick={handleNewSession}
                  className="h-7 px-2.5 rounded bg-[#0f2942] text-white text-xs font-semibold flex items-center gap-1 hover:bg-[#1e3a8a] transition-colors shadow-none"
                  title="Start fresh research session"
                >
                  <Plus size={13} />
                  <span>New Note</span>
                </button>
              </div>

              {/* Target Company Selector */}
              <div className="p-3 border-b border-[#e2e8f0] bg-[#f8fafc]">
                <label className="block font-bold text-[10px] uppercase tracking-wider text-[#64748b] mb-1.5">
                  Target Issuer
                </label>
                <div className="relative">
                  <select 
                    className="w-full h-8 pl-2.5 pr-8 bg-white border border-[#cbd5e1] rounded text-xs text-[#0f172a] font-medium focus:outline-none focus:border-[#0f2942] transition-colors appearance-none cursor-pointer"
                    value={selectedIpoId || ""}
                    onChange={e => {
                      const newId = Number(e.target.value);
                      setSelectedIpoId(newId);
                      handleNewSession();
                    }}
                    disabled={loading}
                  >
                    {ipos.map(ipo => (
                      <option key={ipo.id} value={ipo.id}>
                        {ipo.name} ({ipo.listing_segment || "Mainboard"})
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} className="absolute right-2.5 top-2 text-[#64748b] pointer-events-none" />
                </div>
              </div>

              {/* Search / Filter Rail */}
              <div className="p-2.5 border-b border-[#e2e8f0] bg-white">
                <div className="relative flex items-center">
                  <Search size={13} className="absolute left-2.5 text-[#94a3b8] pointer-events-none" />
                  <input 
                    type="text" 
                    className="w-full h-7 pl-8 pr-2 bg-[#f8fafc] border border-[#e2e8f0] rounded text-xs text-[#0f172a] placeholder:text-[#94a3b8] focus:outline-none focus:border-[#0f2942] transition-colors"
                    placeholder="Filter company or session..."
                    value={sessionFilter}
                    onChange={e => setSessionFilter(e.target.value)}
                  />
                </div>
              </div>

              {/* Session List */}
              <div className="flex-1 divide-y divide-[#f1f5f9] overflow-y-auto max-h-[calc(100vh-25rem)]">
                {filteredSessions.length === 0 ? (
                  <div className="p-6 text-center text-[#64748b]">
                    <Clock size={24} className="mx-auto mb-2 opacity-30" />
                    <p className="text-xs font-medium">No previous research sessions found.</p>
                    <p className="text-[11px] text-[#94a3b8] mt-1">Ask a question below to start your first workstation.</p>
                  </div>
                ) : (
                  filteredSessions.map(sess => {
                    const sessIpo = ipos.find(i => i.id === sess.ipo_id);
                    const isActive = activeSessionId === sess.id;
                    const status = sessIpo?.status || "Live";
                    const statusLower = status.toLowerCase();

                    return (
                      <div 
                        key={sess.id}
                        onClick={() => handleSelectSession(sess)}
                        className={`p-3 cursor-pointer transition-colors group relative ${
                          isActive 
                            ? "bg-[#f1f5f9] border-l-2 border-[#0f2942]" 
                            : "hover:bg-[#f8fafc] border-l-2 border-transparent"
                        }`}
                      >
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className={`font-serif text-xs font-bold truncate ${isActive ? "text-[#001428]" : "text-[#0f172a]"}`}>
                            {sessIpo?.name || "IPO Research"}
                          </span>
                          <span className={`px-1.5 py-0.2 rounded font-mono text-[9px] font-semibold tracking-wide uppercase border ${
                            statusLower === "upcoming" 
                              ? "bg-amber-50 text-amber-900 border-amber-200"
                              : statusLower === "closed"
                              ? "bg-slate-100 text-slate-700 border-slate-200"
                              : "bg-emerald-50 text-emerald-800 border-emerald-200"
                          }`}>
                            {status}
                          </span>
                        </div>

                        <p className="text-[11px] text-[#475569] line-clamp-1 leading-snug mb-1.5">
                          {sess.title}
                        </p>

                        <div className="flex items-center justify-between text-[#64748b] font-mono text-[10px]">
                          <span className="flex items-center gap-1">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                            {date(sess.created_at)}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-[#001428]">
                              {issueSize(sessIpo?.issue_size_crore)}
                            </span>
                            <button
                              onClick={(e) => handleDeleteSession(e, sess.id)}
                              className="opacity-0 group-hover:opacity-100 hover:text-[#b91c1c] transition-opacity p-0.5"
                              title="Delete session"
                            >
                              <Trash2 size={11} />
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })
                )}
              </div>

              {/* Bottom Universe Filter Pills */}
              <div className="p-3 border-t border-[#e2e8f0] bg-[#f8fafc]">
                <div className="font-bold text-[10px] uppercase tracking-wider text-[#64748b] mb-1.5">
                  Universe Scope
                </div>
                <div className="flex items-center gap-1 flex-wrap">
                  {(["ALL", "MAIN", "SME", "DRHP"] as const).map(filter => (
                    <button
                      key={filter}
                      onClick={() => setUniverseFilter(filter)}
                      className={`px-2 py-0.5 rounded text-[10px] font-mono transition-colors ${
                        universeFilter === filter 
                          ? "bg-[#0f2942] text-white font-semibold" 
                          : "bg-white text-[#475569] border border-[#cbd5e1] hover:bg-[#f1f5f9]"
                      }`}
                    >
                      {filter === "ALL" ? `All (${ipos.length})` : filter}
                    </button>
                  ))}
                </div>
              </div>

            </div>
          </aside>

          {/* ════════ COLUMN 2: Institutional Dialogue & Synthesis Notebook (6 cols) ════════ */}
          <section className={`lg:col-span-6 bg-[#faf8ff] flex flex-col justify-between border-r border-[#e2e8f0] ${
            activeTabMobile !== "dialogue" ? "hidden lg:flex" : "flex"
          }`}>
            <div className="flex flex-col h-full">

              {/* Notebook Header Banner */}
              <div className="p-3.5 bg-white border-b border-[#e2e8f0]">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className="px-1.5 py-0.5 rounded bg-[#f1f5f9] text-[#0f2942] font-mono text-[10px] font-bold border border-[#cbd5e1]">
                        EQUITY RESEARCH
                      </span>
                      <span className="font-mono text-[10px] text-[#64748b]">
                        DOC_ID: {selectedIpo?.slug?.toUpperCase() || "IPO"}-DRHP-{activeSessionId || "LIVE"}
                      </span>
                    </div>

                    <h1 className="font-serif font-bold text-base text-[#001428] tracking-tight">
                      {selectedIpo?.name || "Select Issuer"} ({tickerCode}) — Institutional Valuation & Research
                    </h1>

                    <p className="text-xs text-[#475569] mt-1 flex items-center gap-2 flex-wrap">
                      <span>Model: <strong className="text-[#0f172a] font-semibold">Fundamental DCF & Peer Comps</strong></span>
                      <span className="text-[#cbd5e1]">•</span>
                      <span>Price Band: <strong className="font-mono text-[#001428] font-bold">{priceBand(selectedIpo?.price_band)}</strong></span>
                      <span className="text-[#cbd5e1]">•</span>
                      <span>Size: <strong className="font-mono text-[#001428] font-bold">{issueSize(selectedIpo?.issue_size_crore)}</strong></span>
                    </p>
                  </div>

                  <div className="flex items-center gap-1 shrink-0">
                    <button 
                      onClick={handleNewSession}
                      className="p-1.5 rounded border border-[#e2e8f0] text-[#64748b] hover:text-[#001428] hover:bg-[#f8fafc] transition-colors"
                      title="Clear Notebook / New Session"
                    >
                      <Plus size={14} />
                    </button>
                  </div>
                </div>
              </div>

              {/* Dialogue / Feed Stream */}
              <div className="flex-1 p-4 space-y-4 overflow-y-auto max-h-[calc(100vh-22rem)] min-h-[350px]">
                
                {/* Empty State */}
                {messages.length === 0 && !busy && (
                  <div className="py-8 px-4 text-center max-w-lg mx-auto">
                    <div className="w-10 h-10 rounded-full bg-[#f1f5f9] border border-[#e2e8f0] flex items-center justify-center mx-auto mb-3 text-[#0f2942]">
                      <Sparkles size={18} />
                    </div>
                    <h3 className="font-serif font-bold text-sm text-[#001428] mb-1">
                      Institutional Research Notebook
                    </h3>
                    <p className="text-xs text-[#64748b] mb-4 leading-relaxed">
                      Interrogate audited prospectus filings, verify margin trajectories, and synthesize equity valuation models for {selectedIpo?.name || "the selected company"}.
                    </p>
                    <div className="space-y-1.5 text-left">
                      <div className="font-bold text-[10px] uppercase tracking-wider text-[#64748b] mb-1">
                        Suggested Research Prompts
                      </div>
                      {promptSuggestions.map((prompt, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleAsk(prompt)}
                          className="w-full text-left p-2 rounded bg-white hover:bg-[#f8fafc] border border-[#e2e8f0] hover:border-[#0f2942] text-xs text-[#0f172a] transition-all flex items-center justify-between group shadow-none"
                        >
                          <span className="line-clamp-1">{prompt}</span>
                          <Send size={11} className="text-[#94a3b8] group-hover:text-[#0f2942] shrink-0 ml-2" />
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Messages Stream */}
                {messages.map((msg, idx) => {
                  const isUser = msg.role === "user";

                  if (isUser) {
                    return (
                      <div key={idx} className="bg-white border border-[#e2e8f0] rounded p-3.5 shadow-none">
                        <div className="flex items-center justify-between mb-1.5">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded bg-[#0f2942] text-white font-mono text-[10px] flex items-center justify-center font-bold">
                              AN
                            </span>
                            <span className="text-xs font-bold text-[#001428]">
                              Institutional Desk Query
                            </span>
                          </div>
                          <span className="font-mono text-[10px] text-[#64748b]" suppressHydrationWarning>
                            {new Date(msg.created_at).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" })} IST
                          </span>
                        </div>
                        <p className="text-xs text-[#0f172a] font-normal leading-relaxed">
                          {msg.content}
                        </p>
                      </div>
                    );
                  }

                  // Assistant Synthesis Card
                  return (
                    <div key={idx} className="bg-white border border-[#cbd5e1] rounded p-3.5 space-y-3 shadow-none">
                      
                      {/* Synthesis Header */}
                      <div className="flex items-center justify-between border-b border-[#e2e8f0] pb-2 flex-wrap gap-2">
                        <div className="flex items-center gap-2">
                          <span className="px-1.5 py-0.5 rounded bg-[#0f2942] text-white font-mono text-[10px] font-bold">
                            SYNTHESIS
                          </span>
                          <span className="text-xs font-bold text-[#001428]">
                            Financial & Operational Audit Record
                          </span>
                        </div>
                        <span className="font-mono text-[10px] text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 font-semibold">
                          Confidence: SEBI_VERIFIED
                        </span>
                      </div>

                      {/* Tool Trace Log */}
                      {msg.tool_trace && msg.tool_trace.length > 0 && (
                        <div className="flex items-center gap-1.5 font-mono text-[10px] text-[#64748b] bg-[#f8fafc] px-2 py-1 rounded border border-[#e2e8f0]">
                          <span className="font-bold text-[#0f2942]">Trace:</span>
                          <span>{msg.tool_trace.join(" → ")}</span>
                        </div>
                      )}

                      {/* Executive Summary / Answer Text */}
                      <div className="text-xs text-[#0f172a] leading-relaxed whitespace-pre-wrap font-normal">
                        {msg.content}
                      </div>

                      {/* Verified Statements with Citations */}
                      {msg.citations && msg.citations.length > 0 && (
                        <div className="pt-2 border-t border-[#f1f5f9] space-y-2">
                          <div className="font-bold text-[10px] uppercase tracking-wider text-[#64748b]">
                            Verified Prospectus Citations ({msg.citations.length})
                          </div>
                          <div className="space-y-1.5">
                            {msg.citations.map((claim, cIdx) => (
                              <div key={cIdx} className="p-2 rounded bg-[#f8fafc] border border-[#e2e8f0] text-xs">
                                <p className="font-medium text-[#0f172a] mb-1">{claim.text}</p>
                                {claim.citations && claim.citations.map((cite, citeIdx) => (
                                  <div key={citeIdx} className="pl-2 border-l-2 border-[#0f2942] mt-1 text-[11px] text-[#475569]">
                                    <span className="font-mono font-bold text-[#001428] mr-1.5">
                                      DRHP P.{cite.page || "—"} [{cite.section || "Disclosures"}]
                                    </span>
                                    <span className="italic">"{cite.excerpt}"</span>
                                  </div>
                                ))}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                    </div>
                  );
                })}

                {/* Loading State */}
                {busy && (
                  <div className="bg-white border border-[#cbd5e1] rounded p-4 space-y-2.5 animate-pulse shadow-none">
                    <div className="flex items-center gap-2 text-xs font-bold text-[#0f2942]">
                      <span className="w-2 h-2 rounded-full bg-[#0f2942] animate-ping" />
                      <span>Interrogating filing documents & computing valuation models...</span>
                    </div>
                    <div className="h-2 bg-[#f1f5f9] rounded w-3/4" />
                    <div className="h-2 bg-[#f1f5f9] rounded w-5/6" />
                    <div className="h-2 bg-[#f1f5f9] rounded w-2/3" />
                  </div>
                )}

                {/* Error Banner */}
                {error && (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded text-xs text-rose-800 flex items-start gap-2">
                    <AlertTriangle size={14} className="shrink-0 mt-0.5 text-rose-600" />
                    <div>
                      <p className="font-semibold">Analysis Failed</p>
                      <p className="mt-0.5 text-[11px]">{error}</p>
                    </div>
                  </div>
                )}

                <div ref={messageEndRef} />
              </div>

              {/* Dialogue Input Console Bar */}
              <div className="p-3 bg-white border-t border-[#e2e8f0]">
                <div className="relative">
                  <textarea
                    rows={2}
                    value={question}
                    onChange={e => setQuestion(e.target.value)}
                    onKeyDown={e => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        if (!busy) handleAsk();
                      }
                    }}
                    placeholder="Ask a fundamental question, request peer sensitivity model, or verify DRHP risk factors..."
                    disabled={busy}
                    className="w-full p-2.5 bg-white border border-[#cbd5e1] rounded text-xs text-[#0f172a] placeholder:text-[#94a3b8] focus:outline-none focus:border-[#0f2942] transition-colors resize-none shadow-none"
                  />
                </div>

                <div className="flex items-center justify-between mt-2 flex-wrap gap-2">
                  <div className="flex items-center gap-1">
                    <button 
                      onClick={() => handleAsk("What are the key risk factors and litigations disclosed in the DRHP?")}
                      className="h-6 px-2 rounded bg-[#f8fafc] hover:bg-[#f1f5f9] text-[#475569] text-[11px] border border-[#e2e8f0] flex items-center gap-1 transition-colors"
                    >
                      <span>Risk Factors</span>
                    </button>
                    <button 
                      onClick={() => handleAsk("Synthesize revenue CAGR, EBITDA margin, and capital expenditure.")}
                      className="h-6 px-2 rounded bg-[#f8fafc] hover:bg-[#f1f5f9] text-[#475569] text-[11px] border border-[#e2e8f0] flex items-center gap-1 transition-colors"
                    >
                      <span>Financials</span>
                    </button>
                    <button 
                      onClick={() => handleAsk("Why is this IPO valued at its current price band relative to peers?")}
                      className="h-6 px-2 rounded bg-[#f8fafc] hover:bg-[#f1f5f9] text-[#475569] text-[11px] border border-[#e2e8f0] flex items-center gap-1 transition-colors"
                    >
                      <span>Valuation Comps</span>
                    </button>
                  </div>

                  <button
                    onClick={() => handleAsk()}
                    disabled={busy || !question.trim()}
                    className="h-7 px-3 rounded bg-[#0f2942] text-white text-xs font-semibold hover:bg-[#1e3a8a] disabled:opacity-50 transition-colors flex items-center gap-1 shadow-none"
                  >
                    <span>{busy ? "Analyzing..." : "Execute Analysis"}</span>
                    <Send size={11} />
                  </button>
                </div>
              </div>

            </div>
          </section>

          {/* ════════ COLUMN 3: Evidence Dock, Citations & Linked Models (3 cols) ════════ */}
          <aside className={`lg:col-span-3 bg-white flex flex-col justify-between ${
            activeTabMobile !== "evidence" ? "hidden lg:flex" : "flex"
          }`}>
            <div className="flex flex-col h-full">

              {/* Dock Header */}
              <div className="p-3.5 border-b border-[#e2e8f0] flex items-center justify-between bg-white">
                <div className="flex items-center gap-1.5">
                  <ShieldCheck size={16} className="text-[#0f2942]" />
                  <h2 className="font-serif font-bold text-sm text-[#001428]">Evidence Dock</h2>
                </div>
                <span className="font-mono text-[10px] text-[#475569] bg-[#f1f5f9] px-2 py-0.5 rounded border border-[#cbd5e1] font-semibold">
                  {activeCitations.length > 0 ? `${activeCitations.length} CITATIONS` : "PROSPECTUS AUDIT"}
                </span>
              </div>

              {/* Evidence Content Scrollable */}
              <div className="p-3.5 space-y-4 overflow-y-auto max-h-[calc(100vh-22rem)]">
                
                {/* Section 1: Verified Document References */}
                <div>
                  <div className="font-bold text-[10px] uppercase tracking-wider text-[#64748b] mb-2 flex items-center justify-between">
                    <span>Verified Citations (DRHP / RHP)</span>
                    <span className="font-mono text-[9px] text-[#94a3b8]">SEBI VERIFIED</span>
                  </div>

                  {activeCitations.length > 0 ? (
                    <div className="space-y-2">
                      {activeCitations.map((cite, idx) => (
                        <div key={idx} className="p-2.5 border border-[#e2e8f0] rounded bg-[#f8fafc] hover:bg-white transition-colors">
                          <div className="flex items-center justify-between text-[#001428] mb-1">
                            <span className="font-mono text-[11px] font-bold">
                              DRHP P.{cite.page || "—"} [{cite.section || "Table 4.1"}]
                            </span>
                            <span className="font-mono text-[10px] text-[#15803d] font-semibold bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200">
                              DOC #{cite.docId}
                            </span>
                          </div>
                          <p className="text-xs text-[#0f172a] font-medium leading-snug mb-1">
                            "{cite.excerpt}"
                          </p>
                          <div className="font-mono text-[9px] text-[#64748b]">
                            Attributed to: {cite.claimText}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="p-3 border border-dashed border-[#cbd5e1] rounded bg-[#f8fafc] text-center">
                      <FileText size={18} className="mx-auto text-[#94a3b8] mb-1.5" />
                      <p className="text-xs font-semibold text-[#0f172a]">
                        {selectedIpo?.name} Filing Pipeline
                      </p>
                      <p className="text-[11px] text-[#64748b] mt-0.5">
                        Filing status: <span className="font-semibold text-[#001428]">{selectedIpo?.status || "Ingested"}</span>
                      </p>
                      <div className="font-mono text-[10px] text-[#475569] mt-2 pt-2 border-t border-[#e2e8f0]">
                        Ask a question in Center Pane to extract exact source quotes.
                      </div>
                    </div>
                  )}
                </div>

                {/* Section 2: Real-Time Linked Model Inputs */}
                <div className="pt-2 border-t border-[#e2e8f0]">
                  <div className="font-bold text-[10px] uppercase tracking-wider text-[#64748b] mb-2 flex items-center justify-between">
                    <span>Valuation Parameters (Live Link)</span>
                    <span className="font-mono text-[9px] text-emerald-700 font-semibold">SYNCED</span>
                  </div>
                  
                  <div className="border border-[#e2e8f0] rounded p-2.5 bg-[#f8fafc] space-y-1.5 font-mono text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[#64748b]">Issue Size:</span>
                      <span className="font-bold text-[#001428]">{issueSize(selectedIpo?.issue_size_crore)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#64748b]">Price Band:</span>
                      <span className="font-bold text-[#001428]">{priceBand(selectedIpo?.price_band)}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#64748b]">Listing Segment:</span>
                      <span className="font-bold text-[#001428]">{selectedIpo?.listing_segment || "Mainboard"}</span>
                    </div>
                    {scoreData && (
                      <div className="pt-1.5 border-t border-[#e2e8f0] flex items-center justify-between">
                        <span className="text-[#64748b]">Platform IPO Score:</span>
                        <span className="font-bold text-[#0f2942] bg-white px-2 py-0.5 rounded border border-[#cbd5e1]">
                          {scoreOutOfTen(scoreData.overall_score)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>

                {/* Section 3: Risk Factors Summary */}
                {risksData.length > 0 && (
                  <div className="pt-2 border-t border-[#e2e8f0]">
                    <div className="font-bold text-[10px] uppercase tracking-wider text-[#64748b] mb-2 flex items-center justify-between">
                      <span>DRHP Risk Disclosures ({risksData.length})</span>
                      <span className="font-mono text-[9px] text-[#94a3b8]">EXTRACTED</span>
                    </div>
                    <div className="space-y-1.5 max-h-48 overflow-y-auto">
                      {risksData.slice(0, 5).map((risk, idx) => (
                        <div key={idx} className="p-2 rounded border border-[#e2e8f0] bg-[#f8fafc] text-xs">
                          <div className="flex items-center justify-between gap-1 mb-1">
                            <span className="font-bold text-[11px] text-[#001428] truncate">{risk.category}</span>
                            <span className={`font-mono text-[9px] font-bold px-1.5 py-0.2 rounded uppercase border ${
                              risk.severity === "High"
                                ? "bg-rose-50 text-rose-700 border-rose-200"
                                : risk.severity === "Medium"
                                ? "bg-amber-50 text-amber-800 border-amber-200"
                                : "bg-slate-100 text-slate-700 border-slate-200"
                            }`}>
                              {risk.severity}
                            </span>
                          </div>
                          <p className="text-[11px] text-[#475569] line-clamp-2 leading-tight">
                            {risk.summary}
                          </p>
                          {risk.source_page && (
                            <span className="font-mono text-[9px] text-[#64748b] mt-1 block">
                              Source: DRHP Page {risk.source_page}
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              </div>

              {/* Section 4: Analyst Audit Trail & SEBI Disclaimer */}
              <div className="p-3 border-t border-[#e2e8f0] bg-[#f8fafc]">
                <div className="font-bold text-[10px] uppercase tracking-wider text-[#64748b] mb-1">
                  Audit Trail & Attributions
                </div>
                <div className="font-mono text-[9px] text-[#64748b] space-y-0.5 mb-2">
                  <div>DESK: Institutional ECM - IN01</div>
                  <div>ANALYST ID: SEBI-RA-IN0088194</div>
                  <div suppressHydrationWarning>TIMESTAMP: {new Date().toISOString().substring(0, 19)} IST</div>
                </div>
                <p className="text-[10px] text-[#64748b] leading-tight">
                  Disclaimer: Strictly for institutional research and QIB review under SEBI (Research Analysts) Regulations, 2014. Not an offer to buy or sell securities.
                </p>
              </div>

            </div>
          </aside>

        </div>
      </main>

    </div>
  );
}
