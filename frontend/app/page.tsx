"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { getIPOs, IPO } from "../lib/api";
import { date, priceBand, issueSize, scoreOutOfTen } from "../lib/format";

export default function MarketPage() {
  const [ipos, setIpos] = useState<IPO[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getIPOs()
      .then(data => {
        setIpos(data || []);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to fetch IPOs:", err);
        setError("Unable to connect to the IPO data feed. Please ensure the API is running.");
        setLoading(false);
      });
  }, []);

  // Primary lifecycle filtering without record duplication
  const openNow = useMemo(() => ipos.filter(x => x.status === "Ongoing"), [ipos]);
  const upcoming = useMemo(() => ipos.filter(x => x.status === "Upcoming"), [ipos]);
  const recentlyClosed = useMemo(() => ipos.filter(x => x.status === "Closed"), [ipos]);
  const recentlyListed = useMemo(() => ipos.filter(x => x.status === "Listed"), [ipos]);

  // Mainboard count across current active feed
  const mainboardCount = useMemo(
    () => ipos.filter(x => x.listing_segment === "Mainboard").length,
    [ipos]
  );

  // Helper to extract 2-letter fallback initials
  function getInitials(name: string): string {
    if (!name) return "—";
    const words = name.trim().split(/\s+/);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return name.substring(0, 2).toUpperCase();
  }

  // Render unified table for a given set of IPOs
  function renderTable(records: IPO[], segmentLabel: string) {
    if (records.length === 0) {
      return (
        <div className="empty-segment-row">
          No {segmentLabel} issues currently in this window.
        </div>
      );
    }

    return (
      <div className="table-responsive">
        <table className="ipo-data-table">
          <thead>
            <tr>
              <th style={{ width: "32%" }}>Company</th>
              <th style={{ width: "16%" }}>Sector</th>
              <th className="center" style={{ width: "10%" }}>Status</th>
              <th className="num" style={{ width: "13%" }}>Issue Size</th>
              <th className="num" style={{ width: "13%" }}>Price Band</th>
              <th className="num" style={{ width: "14%" }}>Issue Dates</th>
              <th className="center" style={{ width: "12%" }}>IPO Score</th>
            </tr>
          </thead>
          <tbody>
            {records.map(ipo => {
              const initials = getInitials(ipo.name);
              const scoreText = scoreOutOfTen(ipo.score);
              const formattedPrice = priceBand(ipo.price_band);
              const formattedSize = issueSize(ipo.issue_size_crore);
              const formattedDate = date(ipo.issue_date);
              const statusLower = (ipo.status || "").toLowerCase();

              return (
                <tr 
                  key={ipo.id} 
                  onClick={() => window.location.href = `/ipos/${ipo.id}`}
                  title={`View ${ipo.name} details`}
                >
                  {/* Company Cell */}
                  <td>
                    <div className="company-cell">
                      <div className="company-logo-container">
                        {ipo.logo_url ? (
                          <img 
                            src={ipo.logo_url} 
                            alt={ipo.name} 
                            onError={(e) => {
                              (e.currentTarget as HTMLImageElement).style.display = 'none';
                              const fallback = e.currentTarget.parentElement?.querySelector('.company-initials-fallback') as HTMLElement;
                              if (fallback) fallback.style.display = 'block';
                            }} 
                          />
                        ) : null}
                        <span 
                          className="company-initials company-initials-fallback"
                          style={{ display: ipo.logo_url ? 'none' : 'block' }}
                        >
                          {initials}
                        </span>
                      </div>
                      <div className="company-info">
                        <span className="company-name">{ipo.name}</span>
                        <div className="company-meta">
                          <span className="exchange-chip">
                            {ipo.exchange || (ipo.listing_segment === "SME" ? "BSE SME / NSE Emerge" : "NSE / BSE")}
                          </span>
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Sector */}
                  <td>
                    <span style={{ color: "var(--text-secondary)" }}>
                      {(!ipo.sector || ipo.sector.toLowerCase() === "unknown") ? "—" : ipo.sector}
                    </span>
                  </td>

                  {/* Status Badge */}
                  <td className="center">
                    <span className={`badge-status ${statusLower}`}>
                      {(statusLower === "ongoing" || statusLower === "upcoming") && (
                        <span className="status-dot" />
                      )}
                      {ipo.status || "—"}
                    </span>
                  </td>

                  {/* Issue Size */}
                  <td className="num" style={{ fontWeight: 500 }}>
                    {formattedSize}
                  </td>

                  {/* Price Band */}
                  <td className="num">
                    {formattedPrice}
                  </td>

                  {/* Issue Dates */}
                  <td className="num" style={{ color: "var(--text-secondary)" }}>
                    {formattedDate}
                  </td>

                  {/* IPO Score */}
                  <td className="center">
                    {scoreText !== "—" ? (
                      <span className="score-value">
                        {scoreText.split(" / ")[0]}
                        <span className="score-denom"> / 10</span>
                      </span>
                    ) : (
                      <span style={{ color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>—</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    );
  }

  // Render a primary lifecycle section with Mainboard and SME subsections
  function renderSection(
    title: string, 
    items: IPO[]
  ) {
    // Partition strictly by source-backed listing_segment
    const mainboardItems = items.filter(x => x.listing_segment === "Mainboard");
    const smeItems = items.filter(x => x.listing_segment === "SME");

    return (
      <section className="section-container">
        <div className="section-header-bar">
          <div className="section-header-left">
            <h2 className="section-title">{title}</h2>
            <span className="section-badge">
              {items.length} {items.length === 1 ? "Issue" : "Issues"}
            </span>
          </div>
        </div>

        {/* Mainboard subsection */}
        <div className="segment-group">
          <div className="segment-header-bar">
            <span className="segment-title">Mainboard</span>
            <span className="segment-count-tag">
              ({mainboardItems.length} {mainboardItems.length === 1 ? "record" : "records"})
            </span>
          </div>
          {renderTable(mainboardItems, "Mainboard")}
        </div>

        {/* SME subsection */}
        <div className="segment-group">
          <div className="segment-header-bar">
            <span className="segment-title">SME</span>
            <span className="segment-count-tag">
              ({smeItems.length} {smeItems.length === 1 ? "record" : "records"})
            </span>
          </div>
          {renderTable(smeItems, "SME")}
        </div>
      </section>
    );
  }

  return (
    <main className="market-page-container">
      {/* Header & Meta Strip */}
      <header className="market-header-section">
        <div className="market-header-row">
          <div className="market-header-left">
            <h1 className="market-page-title">IPO Market</h1>
            <p className="market-page-subtitle">
              Live IPO tracking and fundamental analysis of Indian IPOs.
            </p>
          </div>
          <div className="market-header-right">
            <div className="market-status-pill">
              <span className="pulse-indicator">
                <span className="pulse-indicator-ping" />
                <span className="pulse-indicator-dot" />
              </span>
              <span>NSE / BSE Mainboard &amp; SME Tracker</span>
              <span style={{ color: "var(--border-strong)" }}>|</span>
              <span style={{ color: "var(--text-muted)" }}>Live Feed</span>
            </div>
          </div>
        </div>

        {/* 4 Key Aggregates Strip */}
        <div className="summary-strip">
          {/* 1. Open Now */}
          <div className="summary-card">
            <div className="summary-card-left">
              <div className="summary-label-row">
                <span className="summary-dot open" />
                <span className="summary-card-title">Open Now</span>
              </div>
              <div className="summary-count-val">
                {openNow.length} {openNow.length === 1 ? "Issue" : "Issues"}
              </div>
            </div>
            <div className="summary-card-right">
              <span className="summary-sub-label">Status</span>
              <div className="summary-sub-val" style={{ color: "var(--badge-open-text)" }}>
                Active
              </div>
            </div>
          </div>

          {/* 2. Upcoming */}
          <div className="summary-card">
            <div className="summary-card-left">
              <div className="summary-label-row">
                <span className="summary-dot upcoming" />
                <span className="summary-card-title">Upcoming</span>
              </div>
              <div className="summary-count-val">
                {upcoming.length} {upcoming.length === 1 ? "Issue" : "Issues"}
              </div>
            </div>
            <div className="summary-card-right">
              <span className="summary-sub-label">Status</span>
              <div className="summary-sub-val" style={{ color: "var(--badge-upcoming-text)" }}>
                Pipeline
              </div>
            </div>
          </div>

          {/* 3. Mainboard */}
          <div className="summary-card">
            <div className="summary-card-left">
              <div className="summary-label-row">
                <span className="summary-dot mainboard" />
                <span className="summary-card-title">Mainboard</span>
              </div>
              <div className="summary-count-val">
                {mainboardCount} {mainboardCount === 1 ? "Issue" : "Issues"}
              </div>
            </div>
            <div className="summary-card-right">
              <span className="summary-sub-label">Segment</span>
              <div className="summary-sub-val">
                NSE / BSE
              </div>
            </div>
          </div>

          {/* 4. Recently Closed */}
          <div className="summary-card">
            <div className="summary-card-left">
              <div className="summary-label-row">
                <span className="summary-dot closed" />
                <span className="summary-card-title">Recently Closed</span>
              </div>
              <div className="summary-count-val">
                {recentlyClosed.length} {recentlyClosed.length === 1 ? "Issue" : "Issues"}
              </div>
            </div>
            <div className="summary-card-right">
              <span className="summary-sub-label">Status</span>
              <div className="summary-sub-val" style={{ color: "var(--text-secondary)" }}>
                Closed
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Error notification banner */}
      {error && (
        <div style={{
          marginBottom: 24,
          padding: "12px 16px",
          backgroundColor: "var(--badge-upcoming-bg)",
          border: "1px solid var(--badge-upcoming-border)",
          color: "var(--badge-upcoming-text)",
          borderRadius: 2,
          fontSize: 13
        }}>
          {error}
        </div>
      )}

      {/* Loading state or Primary Sections */}
      {loading ? (
        <div className="loading-shimmer-box">
          <div className="loading-spinner" />
          <span>Loading market IPO data...</span>
        </div>
      ) : (
        <div className="market-sections-wrapper">
          {/* 1. OPEN NOW */}
          {renderSection("OPEN NOW", openNow)}

          {/* 2. UPCOMING */}
          {renderSection("UPCOMING", upcoming)}

          {/* 3. RECENTLY CLOSED */}
          {renderSection("RECENTLY CLOSED", recentlyClosed)}

          {/* 4. RECENTLY LISTED */}
          {renderSection("RECENTLY LISTED", recentlyListed)}

          {ipos.length === 0 && !error && (
            <div className="empty-segment-row" style={{ textAlign: "center", padding: "48px 16px" }}>
              No active or upcoming IPO records available in the primary market feed.
            </div>
          )}
        </div>
      )}
    </main>
  );
}
