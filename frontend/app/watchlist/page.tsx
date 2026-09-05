"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, getIPOs, IPO } from "../../lib/api";
import { useAuth } from "../../lib/AuthContext";
import { date, priceBand, scoreOutOfTen } from "../../lib/format";

type WatchItem = {
  watchlist_id: number;
  ipo_id: number;
  name: string;
  sector: string;
  status: string;
  score?: number;
  issue_size_crore?: number;
  price_band?: [number, number];
  saved_at?: string;
};

export default function WatchlistPage() {
  const { user, setAuthModalOpen } = useAuth();
  const [items, setItems] = useState<WatchItem[]>([]);
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) {
      setLoading(false);
      return;
    }
    Promise.all([apiFetch("/watchlist"), getIPOs()])
      .then(([watchlist, universe]) => {
        setItems(watchlist);
        setIpos(universe);
      })
      .catch((caught) => setError(caught.message || "Watchlist unavailable."))
      .finally(() => setLoading(false));
  }, [user]);

  if (!user) {
    return (
      <main className="watchlist-page">
        <div className="empty-state panel">
          <span className="overline">Personal monitoring</span>
          <h1>Watchlist</h1>
          <p>Sign in to save IPO research and monitor lifecycle changes.</p>
          <button className="button" onClick={() => setAuthModalOpen(true)}>
            Sign in to view watchlist
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="watchlist-page">
      <header className="page-header">
        <div>
          <span className="overline">Personal monitoring</span>
          <h1>Watchlist</h1>
          <p>Saved IPO research, status and coverage at a glance.</p>
        </div>
        <span className="source-badge">{items.length} saved</span>
      </header>

      {loading ? (
        <div className="panel">Loading watchlist…</div>
      ) : error ? (
        <div className="notice error">{error}</div>
      ) : (
        <div className="watchlist-table panel">
          <div className="watch-head">
            <span>Company</span>
            <span>Status</span>
            <span>Price band</span>
            <span>Issue window</span>
            <span>IPO score</span>
            <span>Coverage</span>
            <span>Saved</span>
          </div>
          {items.length ? (
            items.map((item) => {
              const ipo = ipos.find((candidate) => candidate.id === item.ipo_id);
              return (
                <Link
                  href={`/ipos/${item.ipo_id}`}
                  className="watch-row"
                  key={item.watchlist_id}
                >
                  <div>
                    <b>{item.name}</b>
                    <span>{item.sector || "—"}</span>
                  </div>
                  <span className={`status-badge ${item.status?.toLowerCase() === 'ongoing' ? 'ongoing' : item.status?.toLowerCase() === 'upcoming' ? 'upcoming' : 'listed'}`}>
                    {item.status || "—"}
                  </span>
                  <span>{priceBand(item.price_band)}</span>
                  <span>{date(ipo?.issue_date)}</span>
                  <strong>{scoreOutOfTen(item.score)}</strong>
                  <span>—</span>
                  <span>{date(item.saved_at)}</span>
                </Link>
              );
            })
          ) : (
            <div className="table-empty">No IPOs are saved yet.</div>
          )}
        </div>
      )}
    </main>
  );
}

