"use client";

import { useEffect, useMemo, useState, useRef } from "react";
import Link from "next/link";
import { useAuth } from "../../lib/AuthContext";
import {
  getWatchlist,
  addToWatchlist,
  removeFromWatchlist,
  getIPOs,
  WatchlistItem,
  IPO,
} from "../../lib/api";
import { priceBand, date } from "../../lib/format";
import {
  Bookmark,
  X,
  Download,
  Plus,
  Search,
  ChevronDown,
  ChevronUp,
  FolderOpen,
  Check,
  AlertCircle,
} from "lucide-react";

type FilterTab = "all" | "active" | "upcoming" | "closed";

export default function WatchlistPage() {
  const { user, setAuthModalOpen } = useAuth();
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [universe, setUniverse] = useState<IPO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter & Search states
  const [activeTab, setActiveTab] = useState<FilterTab>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [quickAddOpen, setQuickAddOpen] = useState(false);
  const [smeAccordionOpen, setSmeAccordionOpen] = useState(false);
  const [addingId, setAddingId] = useState<number | null>(null);
  const quickAddRef = useRef<HTMLInputElement>(null);

  // Load user's watchlist and available IPO universe
  const loadData = async () => {
    if (!user) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [watchlistData, universeData] = await Promise.all([
        getWatchlist(),
        getIPOs(),
      ]);
      setItems(watchlistData || []);
      setUniverse(universeData || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load watchlist";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [user]);

  // Remove from watchlist with optimistic update
  const handleRemove = async (e: React.MouseEvent, item: WatchlistItem) => {
    e.stopPropagation();
    const previous = [...items];
    // Optimistic removal
    setItems((current) => current.filter((x) => x.watchlist_id !== item.watchlist_id));

    try {
      await removeFromWatchlist(item.watchlist_id);
    } catch (err: unknown) {
      // Revert if error
      setItems(previous);
      const msg = err instanceof Error ? err.message : "Failed to remove item";
      setError(msg);
    }
  };

  // Add an IPO to watchlist
  const handleAdd = async (ipo: IPO) => {
    setAddingId(ipo.id);
    try {
      await addToWatchlist(ipo.id);
      // Refresh to get complete updated records
      const updated = await getWatchlist();
      setItems(updated);
      setSearchQuery("");
      setQuickAddOpen(false);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add to watchlist";
      setError(msg);
    } finally {
      setAddingId(null);
    }
  };

  // Export CSV
  const handleExportCSV = () => {
    if (items.length === 0) return;
    const headers = [
      "Company",
      "Symbol",
      "Segment",
      "Exchange",
      "Status",
      "Price Band",
      "Issue Size (Cr)",
      "Score (/10)",
      "Issue Window",
      "Saved Date",
    ];
    const rows = items.map((it) => [
      `"${(it.name || "").replace(/"/g, '""')}"`,
      `"${(it.slug || "").toUpperCase()}"`,
      `"${it.listing_segment || "Mainboard"}"`,
      `"${it.exchange || "NSE/BSE"}"`,
      `"${it.status || "—"}"`,
      `"${priceBand(it.price_band)}"`,
      `"${it.issue_size_crore ?? "—"}"`,
      `"${it.score != null ? (it.score / 10).toFixed(1) : "—"}"`,
      `"${formatWindow(it.open_date, it.close_date)}"`,
      `"${it.saved_at ? date(it.saved_at) : "—"}"`,
    ]);
    const csvContent = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `ipo_watchlist_${new Date().toISOString().slice(0, 10)}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 2-Letter Initials Fallback
  const getInitials = (name: string): string => {
    if (!name) return "—";
    const words = name.trim().split(/\s+/);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  // Format issue window date range
  const formatWindow = (open?: string | null, close?: string | null): string => {
    if (!open && !close) return "—";
    if (open && close) {
      try {
        const d1 = new Date(open);
        const d2 = new Date(close);
        if (!isNaN(d1.getTime()) && !isNaN(d2.getTime())) {
          const m1 = d1.toLocaleDateString("en-IN", { month: "short", day: "2-digit" });
          const m2 = d2.toLocaleDateString("en-IN", {
            month: "short",
            day: "2-digit",
            year: "numeric",
          });
          return `${m1} – ${m2}`;
        }
      } catch {}
      return `${open} – ${close}`;
    }
    return open ? date(open) : date(close);
  };

  // Tab counts
  const activeCount = useMemo(
    () => items.filter((x) => x.status?.toLowerCase() === "ongoing").length,
    [items]
  );
  const upcomingCount = useMemo(
    () => items.filter((x) => x.status?.toLowerCase() === "upcoming").length,
    [items]
  );
  const closedCount = useMemo(
    () =>
      items.filter(
        (x) =>
          x.status?.toLowerCase() === "closed" || x.status?.toLowerCase() === "listed"
      ).length,
    [items]
  );

  // Filtered items based on active tab
  const filteredItems = useMemo(() => {
    switch (activeTab) {
      case "active":
        return items.filter((x) => x.status?.toLowerCase() === "ongoing");
      case "upcoming":
        return items.filter((x) => x.status?.toLowerCase() === "upcoming");
      case "closed":
        return items.filter(
          (x) =>
            x.status?.toLowerCase() === "closed" ||
            x.status?.toLowerCase() === "listed"
        );
      case "all":
      default:
        return items;
    }
  }, [items, activeTab]);

  // Aggregate Telemetry
  const aggregateSize = useMemo(() => {
    return items.reduce((acc, curr) => acc + (curr.issue_size_crore || 0), 0);
  }, [items]);

  const avgScore = useMemo(() => {
    const scored = items.filter((x) => x.score != null && !isNaN(x.score));
    if (scored.length === 0) return null;
    const sum = scored.reduce((acc, curr) => acc + (curr.score || 0), 0);
    return sum / scored.length / 10;
  }, [items]);

  // SME segment items
  const smeItems = useMemo(() => {
    return items.filter((x) => x.listing_segment?.toLowerCase() === "sme");
  }, [items]);

  // Quick Add candidates
  const quickAddCandidates = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();
    const watchedIds = new Set(items.map((x) => x.ipo_id));
    return universe
      .filter((ipo) => {
        const nameMatch = ipo.name.toLowerCase().includes(q);
        const slugMatch = ipo.slug.toLowerCase().includes(q);
        const sectorMatch = ipo.sector?.toLowerCase().includes(q);
        return nameMatch || slugMatch || sectorMatch;
      })
      .map((ipo) => ({
        ...ipo,
        isWatched: watchedIds.has(ipo.id),
      }))
      .slice(0, 6);
  }, [searchQuery, universe, items]);

  // If user is not authenticated
  if (!user) {
    return (
      <main className="max-w-7xl mx-auto px-4 md:px-6 pt-20 pb-16 min-h-screen">
        <div className="bg-white border border-slate-200 rounded p-8 md:p-12 text-center max-w-xl mx-auto mt-12 shadow-sm">
          <div className="w-12 h-12 rounded bg-slate-100 border border-slate-200 flex items-center justify-center mx-auto mb-4 text-slate-700">
            <Bookmark size={24} />
          </div>
          <span className="text-[11px] font-mono tracking-wider uppercase text-slate-500 font-semibold block mb-1">
            Personal Monitoring
          </span>
          <h1 className="text-xl font-bold text-[#001428] mb-2 tracking-tight">
            Institutional Watchlist
          </h1>
          <p className="text-sm text-slate-600 mb-6 leading-relaxed">
            Sign in to track IPO candidates, monitor real-time lifecycle transitions, and
            evaluate fundamental scorecard models.
          </p>
          <button
            onClick={() => setAuthModalOpen(true)}
            className="h-9 px-5 inline-flex items-center justify-center gap-2 rounded bg-[#001428] text-white text-xs font-semibold hover:bg-[#0f2942] transition-colors shadow-sm"
          >
            Sign In to Access Watchlist
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="max-w-7xl mx-auto px-4 md:px-6 pt-20 pb-16 min-h-screen">
      {/* Top Workspace Context & Executive Header */}
      <section className="flex flex-col gap-3 mb-5">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-4 pb-4 bg-white p-5 rounded border border-slate-200/80 shadow-sm">
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h1 className="text-2xl font-bold text-[#001428] tracking-tight">
                Watchlist
              </h1>
              <span className="px-2 py-0.5 rounded bg-slate-100 border border-slate-200 text-slate-700 font-mono text-[10px] font-bold tracking-wider leading-none">
                PRIMARY PORTFOLIO
              </span>
            </div>
            <p className="text-xs text-slate-500 max-w-2xl leading-normal">
              Institutional tracking and real-time monitoring of saved IPO candidates across issuance lifecycle.
            </p>
          </div>

          {/* Action Panel */}
          <div className="flex items-center gap-2 shrink-0 flex-wrap">
            <button
              onClick={handleExportCSV}
              className="h-8 px-3 inline-flex items-center gap-1.5 rounded bg-slate-100 border border-slate-200/80 text-slate-700 hover:bg-slate-200/70 transition-colors text-xs font-semibold"
              id="exportCsvBtn"
              title="Download watchlist as CSV"
              disabled={items.length === 0}
            >
              <Download size={14} className="text-slate-500" />
              <span>Export CSV</span>
            </button>
            <button
              onClick={() => {
                setQuickAddOpen(true);
                setTimeout(() => quickAddRef.current?.focus(), 100);
              }}
              className="h-8 px-3 inline-flex items-center gap-1.5 rounded bg-[#001428] text-white hover:bg-[#0f2942] transition-colors text-xs font-semibold shadow-sm"
              id="addCompanyBtn"
              title="Search and add company"
            >
              <Plus size={14} />
              <span>+ Add Company</span>
            </button>
          </div>
        </div>

        {/* Quick Add Search Panel (Expandable) */}
        {quickAddOpen && (
          <div className="bg-white p-3 rounded border border-slate-200 shadow-sm transition-all relative">
            <div className="flex items-center gap-2">
              <Search size={16} className="text-slate-400 shrink-0 pl-1" />
              <input
                ref={quickAddRef}
                type="text"
                className="w-full h-8 px-2 bg-transparent text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none"
                placeholder="Type company name, sector, or ticker to add to tracker..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <button
                onClick={() => {
                  setQuickAddOpen(false);
                  setSearchQuery("");
                }}
                className="p-1 text-slate-400 hover:text-slate-600"
                title="Close search"
              >
                <X size={16} />
              </button>
            </div>

            {/* Candidate Results Dropdown */}
            {searchQuery.trim() && (
              <div className="mt-2 pt-2 border-t border-slate-100 flex flex-col gap-1 max-h-60 overflow-y-auto">
                {quickAddCandidates.length > 0 ? (
                  quickAddCandidates.map((candidate) => (
                    <div
                      key={candidate.id}
                      className="flex items-center justify-between p-2 rounded hover:bg-slate-50 transition-colors text-xs"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-5 h-5 rounded bg-[#001428] text-white flex items-center justify-center font-mono text-[9px] font-bold shrink-0 overflow-hidden">
                          {candidate.logo_url ? (
                            <img
                              src={candidate.logo_url}
                              alt={candidate.name}
                              className="w-full h-full object-contain p-0.5"
                              onError={(e) => {
                                (e.currentTarget as HTMLImageElement).style.display = "none";
                                const fb = e.currentTarget.parentElement?.querySelector(".candidate-initials") as HTMLElement;
                                if (fb) fb.style.display = "block";
                              }}
                            />
                          ) : null}
                          <span className="candidate-initials" style={{ display: candidate.logo_url ? "none" : "block" }}>
                            {getInitials(candidate.name)}
                          </span>
                        </div>
                        <div>
                          <span className="font-semibold text-slate-900 mr-2">
                            {candidate.name}
                          </span>
                          <span className="text-slate-400 font-mono text-[10px]">
                            {candidate.listing_segment || "Mainboard"} • {candidate.status}
                          </span>
                        </div>
                      </div>
                      <div>
                        {candidate.isWatched ? (
                          <span className="text-[11px] font-mono text-emerald-700 font-medium px-2 py-0.5 bg-emerald-50 rounded border border-emerald-200">
                            Tracked
                          </span>
                        ) : (
                          <button
                            onClick={() => handleAdd(candidate)}
                            disabled={addingId === candidate.id}
                            className="h-6 px-2.5 rounded bg-[#001428] text-white text-[11px] font-semibold hover:bg-[#0f2942] transition-colors"
                          >
                            {addingId === candidate.id ? "Adding…" : "+ Add"}
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-xs text-slate-400 p-2 text-center">
                    No matching IPO found in active universe.
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Filter Tab Bar & Real-time Metrics Row */}
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3 bg-white px-3.5 py-2 rounded border border-slate-200/80 shadow-sm">
          {/* Tabs */}
          <div className="flex items-center overflow-x-auto gap-1" id="watchlistTabs">
            <button
              onClick={() => setActiveTab("all")}
              className={`h-7 px-3 rounded text-xs font-semibold whitespace-nowrap transition-all ${
                activeTab === "all"
                  ? "bg-[#001428] text-white shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              All Tracked ({items.length})
            </button>
            <button
              onClick={() => setActiveTab("active")}
              className={`h-7 px-3 rounded text-xs whitespace-nowrap transition-all ${
                activeTab === "active"
                  ? "bg-[#001428] text-white font-semibold shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Bidding Active ({activeCount})
            </button>
            <button
              onClick={() => setActiveTab("upcoming")}
              className={`h-7 px-3 rounded text-xs whitespace-nowrap transition-all ${
                activeTab === "upcoming"
                  ? "bg-[#001428] text-white font-semibold shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Upcoming Pipeline ({upcomingCount})
            </button>
            <button
              onClick={() => setActiveTab("closed")}
              className={`h-7 px-3 rounded text-xs whitespace-nowrap transition-all ${
                activeTab === "closed"
                  ? "bg-[#001428] text-white font-semibold shadow-xs"
                  : "text-slate-600 hover:text-slate-900 hover:bg-slate-100"
              }`}
            >
              Recently Closed ({closedCount})
            </button>
          </div>

          {/* Quick Telemetry Chips */}
          <div className="flex items-center gap-3 shrink-0 font-mono text-[11px] text-slate-500">
            <div className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-600" />
              <span className="text-slate-900 font-semibold tracking-wide">ACTIVE FEED</span>
            </div>
            <span className="text-slate-300">/</span>
            <span>
              AGGREGATE SIZE:{" "}
              <strong className="text-slate-900 font-semibold">
                {aggregateSize > 0
                  ? `₹${aggregateSize.toLocaleString("en-IN", { maximumFractionDigits: 1 })} Cr`
                  : "—"}
              </strong>
            </span>
            <span className="text-slate-300">/</span>
            <span>
              AVG COMP SCORE:{" "}
              <strong className="text-slate-900 font-semibold">
                {avgScore !== null ? avgScore.toFixed(1) : "—"}
              </strong>
            </span>
          </div>
        </div>
      </section>

      {/* Error state display */}
      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-800 rounded text-xs flex items-center gap-2">
          <AlertCircle size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Loading state */}
      {loading ? (
        <div className="bg-white rounded border border-slate-200 p-12 text-center text-slate-500 text-xs font-mono">
          Loading institutional watchlist…
        </div>
      ) : items.length === 0 ? (
        /* Empty State */
        <section className="bg-white rounded border border-slate-200 p-10 md:p-14 text-center shadow-sm mb-6">
          <div className="w-12 h-12 rounded bg-slate-100 border border-slate-200 flex items-center justify-center mx-auto mb-3 text-slate-600">
            <FolderOpen size={22} />
          </div>
          <h3 className="text-base font-bold text-slate-900 mb-1">
            No IPOs currently tracked in primary portfolio
          </h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto mb-5 leading-normal">
            Your institutional watchlist is currently empty. Track active and upcoming IPOs
            from the Market directory or quick-add candidates above.
          </p>
          <div className="flex items-center justify-center gap-3">
            <Link
              href="/"
              className="h-8 px-4 inline-flex items-center justify-center rounded bg-[#001428] text-white hover:bg-[#0f2942] transition-colors text-xs font-semibold shadow-sm"
            >
              Browse Market Directory
            </Link>
            <button
              onClick={() => {
                setQuickAddOpen(true);
                setTimeout(() => quickAddRef.current?.focus(), 100);
              }}
              className="h-8 px-4 inline-flex items-center justify-center rounded bg-slate-100 border border-slate-200 text-slate-700 hover:bg-slate-200/70 transition-colors text-xs font-semibold"
            >
              Quick Add Candidate
            </button>
          </div>
        </section>
      ) : (
        /* Main Institutional Monitoring Table */
        <section className="bg-white rounded border border-slate-200 shadow-sm overflow-hidden mb-6">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[850px]" id="monitoringTable">
              <thead>
                <tr className="h-8 bg-slate-50 border-b border-slate-200 text-slate-500 font-mono text-[10px] tracking-wider uppercase select-none">
                  <th className="px-3.5 py-1.5 font-semibold">Company</th>
                  <th className="px-3.5 py-1.5 font-semibold">Status</th>
                  <th className="px-3.5 py-1.5 font-semibold">Issue Window</th>
                  <th className="px-3.5 py-1.5 font-semibold text-right">Price Band</th>
                  <th className="px-3.5 py-1.5 font-semibold text-right">Issue Size</th>
                  <th className="px-3.5 py-1.5 font-semibold text-center">Score</th>
                  <th className="px-3.5 py-1.5 font-semibold text-right">Saved</th>
                  <th className="px-2 py-1.5 font-semibold text-center w-12"></th>
                </tr>
              </thead>
              <tbody className="text-xs divide-y divide-slate-100 text-slate-900" id="tableBody">
                {filteredItems.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-8 text-center text-slate-400 text-xs font-mono">
                      No issues match the selected &quot;{activeTab}&quot; filter.
                    </td>
                  </tr>
                ) : (
                  filteredItems.map((item) => {
                    const statusLower = item.status?.toLowerCase() || "";
                    const initials = getInitials(item.name);
                    const formattedScore =
                      item.score != null && !isNaN(item.score)
                        ? (item.score / 10).toFixed(1)
                        : null;

                    return (
                      <tr
                        key={item.watchlist_id}
                        className="group h-[38px] hover:bg-slate-50/80 transition-colors cursor-pointer"
                        onClick={() => (window.location.href = `/ipos/${item.ipo_id}`)}
                      >
                        {/* Company Column */}
                        <td className="px-3.5 py-2">
                          <div className="flex items-center gap-2.5">
                            <div className="w-6 h-6 rounded bg-[#001428] text-white flex items-center justify-center font-mono text-[10px] font-bold shrink-0 overflow-hidden">
                              {item.logo_url ? (
                                <img
                                  src={item.logo_url}
                                  alt={item.name}
                                  className="w-full h-full object-contain p-0.5"
                                  onError={(e) => {
                                    (e.currentTarget as HTMLImageElement).style.display = "none";
                                    const fb = e.currentTarget.parentElement?.querySelector(".item-initials") as HTMLElement;
                                    if (fb) fb.style.display = "block";
                                  }}
                                />
                              ) : null}
                              <span className="item-initials" style={{ display: item.logo_url ? "none" : "block" }}>
                                {initials}
                              </span>
                            </div>
                            <div className="flex flex-col">
                              <span className="font-semibold text-slate-900 tracking-tight group-hover:text-blue-900 transition-colors">
                                {item.name}
                              </span>
                              <div className="flex items-center gap-1 font-mono text-[10px] text-slate-500">
                                <span>{(item.slug || "").toUpperCase()}</span>
                                <span className="text-slate-300">•</span>
                                <span>{item.listing_segment || "Mainboard"}</span>
                              </div>
                            </div>
                          </div>
                        </td>

                        {/* Status Column */}
                        <td className="px-3.5 py-2">
                          {statusLower === "ongoing" ? (
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200/80 font-mono text-[11px] font-medium">
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                              Open Now (Live Bidding)
                            </span>
                          ) : statusLower === "upcoming" ? (
                            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200/80 font-mono text-[11px] font-medium">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                              Upcoming Pipeline
                            </span>
                          ) : statusLower === "closed" ? (
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-mono text-[11px] font-medium">
                              Closed (Allotment)
                            </span>
                          ) : (
                            <span className="inline-flex items-center px-2 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 font-mono text-[11px] font-medium">
                              {item.status || "—"}
                            </span>
                          )}
                        </td>

                        {/* Issue Window */}
                        <td className="px-3.5 py-2 font-mono text-[11px] text-slate-600">
                          {formatWindow(item.open_date, item.close_date)}
                        </td>

                        {/* Price Band */}
                        <td className="px-3.5 py-2 font-mono text-[11px] text-right font-medium text-slate-800">
                          {priceBand(item.price_band)}
                        </td>

                        {/* Issue Size */}
                        <td className="px-3.5 py-2 font-mono text-[11px] text-right font-medium text-slate-800">
                          {item.issue_size_crore != null &&
                          !isNaN(item.issue_size_crore) &&
                          item.issue_size_crore > 0
                            ? `₹${item.issue_size_crore.toLocaleString("en-IN", {
                                maximumFractionDigits: 1,
                              })} Cr`
                            : "—"}
                        </td>

                        {/* Score */}
                        <td className="px-3.5 py-2 text-center">
                          {formattedScore !== null ? (
                            <span className="inline-block font-mono text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-100 border border-slate-200/80 text-slate-900">
                              {formattedScore}{" "}
                              <span className="text-slate-400 font-normal text-[10px]">
                                / 10
                              </span>
                            </span>
                          ) : (
                            <span className="font-mono text-slate-400 text-xs">—</span>
                          )}
                        </td>

                        {/* Saved Date */}
                        <td className="px-3.5 py-2 text-right font-mono text-[11px] text-slate-500">
                          {item.saved_at ? date(item.saved_at) : "—"}
                        </td>

                        {/* Actions */}
                        <td className="px-2 py-2 text-center">
                          <div className="flex items-center justify-center gap-1">
                            <span
                              className="text-blue-900 p-1"
                              title="Saved to Watchlist"
                            >
                              <Bookmark size={15} className="fill-blue-900 text-blue-900" />
                            </span>
                            <button
                              onClick={(e) => handleRemove(e, item)}
                              className="text-slate-400 hover:text-red-600 p-1 rounded transition-colors"
                              title="Remove from Watchlist"
                            >
                              <X size={15} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          {/* Live Status Strip */}
          <div className="px-4 py-2 bg-slate-50 border-t border-slate-200 flex flex-col sm:flex-row items-center justify-between gap-2 text-slate-500 font-mono text-[11px]">
            <div className="flex items-center gap-3">
              <span>
                Displaying{" "}
                <span className="text-slate-900 font-semibold" id="visibleRowCount">
                  {filteredItems.length}
                </span>{" "}
                of {items.length} tracked issues
              </span>
              <span>•</span>
              <span>Synced with database</span>
            </div>
            <div className="flex items-center gap-2 text-slate-500">
              <span>Click row to open intelligence breakdown</span>
              <kbd className="px-1 py-0.5 bg-white border border-slate-200 rounded text-[10px] text-slate-700 shadow-2xs font-mono">
                ↵ ENTER
              </kbd>
            </div>
          </div>
        </section>
      )}

      {/* Secondary Workspace / SME Watchlist Accordion */}
      <section className="bg-white rounded border border-slate-200 shadow-sm overflow-hidden mb-6">
        <div
          onClick={() => setSmeAccordionOpen(!smeAccordionOpen)}
          className="flex items-center justify-between px-4 py-3 bg-slate-50 border-b border-slate-200 cursor-pointer select-none hover:bg-slate-100/70 transition-colors"
        >
          <div className="flex items-center gap-2">
            {smeAccordionOpen ? (
              <ChevronUp size={16} className="text-slate-600" />
            ) : (
              <ChevronDown size={16} className="text-slate-600" />
            )}
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-900 text-xs">
                SME Watchlist
              </span>
              <span className="px-1.5 py-0.5 rounded bg-slate-200/80 text-slate-700 font-mono text-[10px] font-semibold">
                {smeItems.length} items
              </span>
            </div>
          </div>
          <span className="font-mono text-[10px] text-slate-500 uppercase tracking-wider">
            Segment: BSE SME / NSE EMERGE
          </span>
        </div>

        {smeAccordionOpen && (
          <div>
            {smeItems.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse min-w-[700px]">
                  <thead>
                    <tr className="h-7 bg-white text-slate-400 font-mono text-[10px] uppercase border-b border-slate-100">
                      <th className="px-4 py-1.5 font-semibold">Company</th>
                      <th className="px-4 py-1.5 font-semibold">Status</th>
                      <th className="px-4 py-1.5 font-semibold text-right">Price Band</th>
                      <th className="px-4 py-1.5 font-semibold text-right">Issue Size</th>
                      <th className="px-4 py-1.5 font-semibold text-center">Score</th>
                      <th className="px-4 py-1.5 font-semibold text-center w-12"></th>
                    </tr>
                  </thead>
                  <tbody className="text-xs divide-y divide-slate-100">
                    {smeItems.map((item) => (
                      <tr
                        key={item.watchlist_id}
                        className="hover:bg-slate-50 transition-colors cursor-pointer"
                        onClick={() => (window.location.href = `/ipos/${item.ipo_id}`)}
                      >
                        <td className="px-4 py-2 font-semibold text-slate-900">
                          {item.name}
                        </td>
                        <td className="px-4 py-2 font-mono text-[11px] text-slate-600">
                          {item.status}
                        </td>
                        <td className="px-4 py-2 font-mono text-[11px] text-right text-slate-800">
                          {priceBand(item.price_band)}
                        </td>
                        <td className="px-4 py-2 font-mono text-[11px] text-right text-slate-800">
                          {item.issue_size_crore
                            ? `₹${item.issue_size_crore} Cr`
                            : "—"}
                        </td>
                        <td className="px-4 py-2 text-center font-mono text-[11px] font-semibold text-slate-900">
                          {item.score != null ? (item.score / 10).toFixed(1) : "—"}
                        </td>
                        <td className="px-4 py-2 text-center">
                          <button
                            onClick={(e) => handleRemove(e, item)}
                            className="text-slate-400 hover:text-red-600 p-1 rounded"
                            title="Remove"
                          >
                            <X size={14} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="p-8 flex flex-col items-center justify-center text-center">
                <div className="w-9 h-9 rounded bg-slate-100 border border-slate-200 flex items-center justify-center mb-2.5 text-slate-500">
                  <FolderOpen size={18} />
                </div>
                <h4 className="text-xs font-bold text-slate-900 mb-1">
                  No SME issues currently tracked
                </h4>
                <p className="text-xs text-slate-500 max-w-sm mb-4 leading-normal">
                  Use the Market directory or company detail view to add emerging growth issues.
                </p>
                <Link
                  href="/"
                  className="h-7 px-3 inline-flex items-center justify-center rounded bg-slate-100 border border-slate-200 text-slate-700 hover:bg-slate-200/80 transition-colors text-xs font-semibold"
                >
                  Browse SME Directory
                </Link>
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
