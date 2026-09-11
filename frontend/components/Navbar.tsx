"use client";
import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "../lib/AuthContext";
import { searchGlobal, SearchResultItem } from "../lib/api";
import { LogOut, User, Search, X, Loader2, FileText } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout, setAuthModalOpen } = useAuth();

  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);

  const containerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);

  // Keyboard shortcut: Cmd/Ctrl + K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
        if (query.trim()) setIsOpen(true);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [query]);

  // Dismiss dropdown on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Close dropdown on route change
  useEffect(() => {
    setIsOpen(false);
    setQuery("");
  }, [pathname]);

  // Debounced query handler
  const handleQueryChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setQuery(val);
    setSelectedIndex(-1);
    setSearchError(null);

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    if (!val.trim()) {
      setResults([]);
      setIsSearching(false);
      setIsOpen(false);
      return;
    }

    setIsOpen(true);
    setIsSearching(true);

    debounceTimerRef.current = setTimeout(async () => {
      try {
        const data = await searchGlobal(val, 8);
        setResults(data.items || []);
      } catch (err: unknown) {
        setSearchError(err instanceof Error ? err.message : "Search failed");
        setResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 250);
  };

  // Navigate to result
  const handleSelectResult = (item: SearchResultItem) => {
    setIsOpen(false);
    setQuery("");
    router.push(`/ipos/${item.id}`);
  };

  // Keyboard navigation within dropdown
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!isOpen) {
      if (e.key === "ArrowDown" && query.trim()) {
        setIsOpen(true);
        e.preventDefault();
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (results.length > 0) {
        setSelectedIndex((prev) => (prev + 1) % results.length);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (results.length > 0) {
        setSelectedIndex((prev) => (prev - 1 + results.length) % results.length);
      }
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (results.length > 0) {
        const target = selectedIndex >= 0 && selectedIndex < results.length ? results[selectedIndex] : results[0];
        handleSelectResult(target);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsOpen(false);
      inputRef.current?.blur();
    }
  };

  const getInitials = (name: string): string => {
    if (!name) return "—";
    const words = name.trim().split(/\s+/);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  };

  return (
    <header className="navbar-wrapper">
      <div className="navbar-inner">
        <div className="nav-brand-group">
          <Link className="brand-wordmark" href="/">
            <span className="brand-text">IPO Intelligence</span>
          </Link>
          <nav className="navlinks">
            <Link href="/" className={`navlink ${pathname === "/" ? "active" : ""}`}>
              Market
            </Link>
            <Link href="/research" className={`navlink ${pathname.startsWith("/research") ? "active" : ""}`}>
              Research
            </Link>
            <Link href="/watchlist" className={`navlink ${pathname.startsWith("/watchlist") ? "active" : ""}`}>
              Watchlist
            </Link>
          </nav>
        </div>

        <div className="nav-actions">
          <div className="search-bar" ref={containerRef}>
            <Search size={14} className="search-icon" />
            <input
              ref={inputRef}
              type="text"
              className="search-input"
              placeholder="Search companies, sectors, DRHP..."
              value={query}
              onChange={handleQueryChange}
              onFocus={() => {
                if (query.trim()) setIsOpen(true);
              }}
              onKeyDown={handleInputKeyDown}
            />
            {query ? (
              <button
                type="button"
                onClick={() => {
                  setQuery("");
                  setResults([]);
                  setIsOpen(false);
                  inputRef.current?.focus();
                }}
                className="p-1 mr-1 text-slate-400 hover:text-slate-600 transition-colors"
                title="Clear search"
              >
                <X size={13} />
              </button>
            ) : (
              <div className="kbd-shortcut">
                <kbd>⌘</kbd>
                <kbd>K</kbd>
              </div>
            )}

            {/* Dropdown Results */}
            {isOpen && query.trim() && (
              <div
                className="absolute top-[calc(100%+4px)] right-0 w-[380px] max-w-[90vw] bg-white border border-slate-200 rounded shadow-xl z-50 overflow-hidden text-left"
                style={{ fontFamily: "var(--font-analytical)" }}
              >
                {/* Header state */}
                {isSearching ? (
                  <div className="p-4 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
                    <Loader2 size={14} className="animate-spin text-slate-400" />
                    <span>Searching IPO universe…</span>
                  </div>
                ) : searchError ? (
                  <div className="p-4 text-center text-xs text-red-600">
                    Search unavailable. Please try again.
                  </div>
                ) : results.length === 0 ? (
                  <div className="p-4 text-center text-xs text-slate-500">
                    No matching companies, IPOs, or filings.
                  </div>
                ) : (
                  <>
                    <div className="max-h-[360px] overflow-y-auto divide-y divide-slate-100">
                      {results.map((item, idx) => {
                        const isSelected = selectedIndex === idx;
                        const statusLower = item.status?.toLowerCase() || "";
                        const initials = getInitials(item.name);
                        return (
                          <div
                            key={item.id}
                            onClick={() => handleSelectResult(item)}
                            onMouseEnter={() => setSelectedIndex(idx)}
                            className={`p-2.5 flex items-center justify-between gap-2.5 cursor-pointer transition-colors ${isSelected ? "bg-slate-100" : "hover:bg-slate-50"
                              }`}
                          >
                            <div className="flex items-center gap-2.5 min-w-0">
                              <div className="w-6 h-6 rounded bg-[#001428] text-white flex items-center justify-center font-mono text-[9px] font-bold shrink-0 overflow-hidden">
                                {item.logo_url ? (
                                  <img
                                    src={item.logo_url}
                                    alt={item.name}
                                    className="w-full h-full object-contain p-0.5"
                                    onError={(e) => {
                                      (e.currentTarget as HTMLImageElement).style.display = "none";
                                      const fb = e.currentTarget.parentElement?.querySelector(".fallback-initials") as HTMLElement;
                                      if (fb) fb.style.display = "block";
                                    }}
                                  />
                                ) : null}
                                <span className="fallback-initials" style={{ display: item.logo_url ? "none" : "block" }}>
                                  {initials}
                                </span>
                              </div>
                              <div className="min-w-0 flex flex-col">
                                <div className="flex items-center gap-1.5 flex-wrap">
                                  <span className="font-semibold text-xs text-slate-900 truncate">
                                    {item.name}
                                  </span>
                                  {item.filing_type && (
                                    <span className="px-1 py-0.2 rounded bg-blue-50 text-blue-700 border border-blue-200 font-mono text-[9px] font-semibold flex items-center gap-0.5">
                                      <FileText size={9} />
                                      {item.filing_type}
                                    </span>
                                  )}
                                </div>
                                <div className="flex items-center gap-1 font-mono text-[10px] text-slate-500 truncate">
                                  <span>{item.slug.toUpperCase()}</span>
                                  <span className="text-slate-300">•</span>
                                  <span>{item.listing_segment}</span>
                                  {item.sector && (
                                    <>
                                      <span className="text-slate-300">•</span>
                                      <span className="truncate">{item.sector}</span>
                                    </>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-2 shrink-0">
                              {statusLower === "ongoing" ? (
                                <span className="px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono text-[10px] font-medium flex items-center gap-1">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                                  Open
                                </span>
                              ) : statusLower === "upcoming" ? (
                                <span className="px-1.5 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 font-mono text-[10px] font-medium">
                                  Upcoming
                                </span>
                              ) : statusLower === "closed" ? (
                                <span className="px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200 font-mono text-[10px] font-medium">
                                  Closed
                                </span>
                              ) : (
                                <span className="px-1.5 py-0.5 rounded bg-blue-50 text-blue-800 border border-blue-200 font-mono text-[10px] font-medium">
                                  {item.status}
                                </span>
                              )}

                              {item.score != null && !isNaN(item.score) && (
                                <span className="font-mono text-[10px] font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded border border-slate-200">
                                  {(item.score / 10).toFixed(1)}
                                </span>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    <div className="px-3 py-1.5 bg-slate-50 border-t border-slate-200 flex items-center justify-between text-[10px] font-mono text-slate-400">
                      <span>{results.length} results</span>
                      <span>↑↓ navigate • ↵ select • esc close</span>
                    </div>
                  </>
                )}
              </div>
            )}
          </div>

          <div className="nav-divider" />

          {!loading && (
            user ? (
              <div className="user-profile">
                <div className="user-info">
                  <User size={13} className="user-icon" />
                  <span className="user-email">{user.email}</span>
                </div>
                <button onClick={logout} className="logout-btn" title="Log out">
                  <LogOut size={13} />
                  <span>Log out</span>
                </button>
              </div>
            ) : (
              <button
                className="btn-signin"
                onClick={() => setAuthModalOpen(true)}
              >
                Sign In
              </button>
            )
          )}
        </div>
      </div>
    </header>
  );
}
