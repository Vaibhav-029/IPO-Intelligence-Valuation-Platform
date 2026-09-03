"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { Users, Info } from "lucide-react";

type Any = Record<string, any>;

type PeerComparisonProps = {
  ipoId: number;
};

const n = (value: any, suffix = "") =>
  value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}${suffix}`;

const premiumFormat = (value: any) => {
  if (value === null || value === undefined) return "—";
  const num = Number(value);
  const color = num > 0 ? "var(--rose)" : num < 0 ? "var(--cyan)" : "var(--muted)";
  const text = num > 0 ? `+${num.toFixed(1)}%` : `${num.toFixed(1)}%`;
  return <span style={{ color }}>{text}</span>;
};

export default function PeerComparison({ ipoId }: PeerComparisonProps) {
  const [data, setData] = useState<Any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchPeers = async () => {
      try {
        const res = await apiFetch(`/ipos/${ipoId}/peers`);
        if (active) setData(res);
      } catch (e) {
        console.error(e);
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchPeers();
    return () => {
      active = false;
    };
  }, [ipoId]);

  if (loading) return null;
  if (!data || !data.peers || data.peers.length === 0) return null;

  const target = data.target;
  const peers = data.peers;
  const stats = data.peer_statistics;
  const comp = data.comparison;

  return (
    <div className="panel glass-panel" style={{ gridColumn: "1 / -1", marginTop: "var(--space-xl)", animation: "fadeInUp 0.8s ease-out" }}>
      <div className="section-title" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Users color="var(--cyan)" size={20} /> Peer Comparison
        </h2>
        <span className="chip">Sector: {target?.sector || "N/A"}</span>
      </div>

      <div style={{ overflowX: "auto", marginTop: 16 }}>
        <table className="table" style={{ width: "100%", textAlign: "left", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", color: "var(--muted)" }}>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>Company</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>Context</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>Mkt Cap (Cr)</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>P/E</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>P/S</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>EV/EBITDA</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>EV/Sales</th>
            </tr>
          </thead>
          <tbody>
            {/* Target Company Rows (Bands) */}
            <tr style={{ backgroundColor: "rgba(0, 255, 204, 0.05)" }}>
              <td style={{ padding: "16px 8px", fontWeight: 600, color: "var(--cyan)" }} rowSpan={2}>
                {target?.name} (Target)
              </td>
              <td style={{ padding: "8px", fontSize: "0.85em", color: "var(--cyan)" }}>Lower Band (IPO)</td>
              <td style={{ padding: "8px" }}>{target?.lower_band?.implied_market_cap ? `₹${Math.round(target.lower_band.implied_market_cap).toLocaleString()}` : "—"}</td>
              <td style={{ padding: "8px" }}>{n(target?.lower_band?.pe, "x")}</td>
              <td style={{ padding: "8px" }}>{n(target?.lower_band?.ps, "x")}</td>
              <td style={{ padding: "8px" }}>{n(target?.lower_band?.ev_ebitda, "x")}</td>
              <td style={{ padding: "8px" }}>{n(target?.lower_band?.ev_sales, "x")}</td>
            </tr>
            <tr style={{ backgroundColor: "rgba(0, 255, 204, 0.05)", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
              <td style={{ padding: "8px", fontSize: "0.85em", color: "var(--cyan)" }}>Upper Band (IPO)</td>
              <td style={{ padding: "8px" }}>{target?.upper_band?.implied_market_cap ? `₹${Math.round(target.upper_band.implied_market_cap).toLocaleString()}` : "—"}</td>
              <td style={{ padding: "8px" }}>{n(target?.upper_band?.pe, "x")}</td>
              <td style={{ padding: "8px" }}>{n(target?.upper_band?.ps, "x")}</td>
              <td style={{ padding: "8px" }}>{n(target?.upper_band?.ev_ebitda, "x")}</td>
              <td style={{ padding: "8px" }}>{n(target?.upper_band?.ev_sales, "x")}</td>
            </tr>

            {/* Peer Rows */}
            {peers.map((peer: Any, idx: number) => (
              <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <td style={{ padding: "16px 8px" }}>{peer.name}</td>
                <td style={{ padding: "16px 8px", color: "var(--muted)", fontSize: "0.85em" }}>Market ({peer.valuation_date})</td>
                <td style={{ padding: "16px 8px", color: "var(--muted)" }}>{peer.market_cap ? `₹${Math.round(peer.market_cap).toLocaleString()}` : "—"}</td>
                <td style={{ padding: "16px 8px", color: "var(--ink)" }}>{n(peer.pe, "x")}</td>
                <td style={{ padding: "16px 8px", color: "var(--ink)" }}>{n(peer.ps, "x")}</td>
                <td style={{ padding: "16px 8px", color: "var(--ink)" }}>{n(peer.ev_ebitda, "x")}</td>
                <td style={{ padding: "16px 8px", color: "var(--ink)" }}>{n(peer.ev_sales, "x")}</td>
              </tr>
            ))}
            
            {/* Median Row */}
            <tr style={{ backgroundColor: "rgba(255,255,255,0.02)" }}>
              <td style={{ padding: "16px 8px", color: "var(--muted)", fontStyle: "italic" }}>Peer Median</td>
              <td style={{ padding: "16px 8px", color: "var(--muted)", fontSize: "0.85em" }}></td>
              <td style={{ padding: "16px 8px" }}></td>
              <td style={{ padding: "16px 8px", color: "var(--ink)" }}>
                {n(stats?.pe?.median, "x")} <span style={{fontSize: "0.75em", color: "var(--dimmed)"}}>(n={stats?.pe?.observations})</span>
              </td>
              <td style={{ padding: "16px 8px", color: "var(--ink)" }}>
                {n(stats?.ps?.median, "x")} <span style={{fontSize: "0.75em", color: "var(--dimmed)"}}>(n={stats?.ps?.observations})</span>
              </td>
              <td style={{ padding: "16px 8px", color: "var(--ink)" }}>
                {n(stats?.ev_ebitda?.median, "x")} <span style={{fontSize: "0.75em", color: "var(--dimmed)"}}>(n={stats?.ev_ebitda?.observations})</span>
              </td>
              <td style={{ padding: "16px 8px", color: "var(--ink)" }}>
                {n(stats?.ev_sales?.median, "x")} <span style={{fontSize: "0.75em", color: "var(--dimmed)"}}>(n={stats?.ev_sales?.observations})</span>
              </td>
            </tr>

            {/* Comparison Rows */}
            <tr style={{ borderTop: "1px solid rgba(255,255,255,0.1)" }}>
              <td style={{ padding: "12px 8px", color: "var(--muted)" }} rowSpan={2}>Premium / Discount</td>
              <td style={{ padding: "4px 8px", fontSize: "0.85em", color: "var(--muted)" }}>Lower Band</td>
              <td style={{ padding: "4px 8px" }}></td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.lower_band?.pe)}</td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.lower_band?.ps)}</td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.lower_band?.ev_ebitda)}</td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.lower_band?.ev_sales)}</td>
            </tr>
            <tr>
              <td style={{ padding: "4px 8px", fontSize: "0.85em", color: "var(--muted)" }}>Upper Band</td>
              <td style={{ padding: "4px 8px" }}></td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.upper_band?.pe)}</td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.upper_band?.ps)}</td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.upper_band?.ev_ebitda)}</td>
              <td style={{ padding: "4px 8px" }}>{premiumFormat(comp?.upper_band?.ev_sales)}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 24, display: "flex", gap: 8, fontSize: 13, color: "var(--dimmed)", backgroundColor: "rgba(255,255,255,0.02)", padding: "12px", borderRadius: 8 }}>
        <Info size={16} />
        <div>
          Target valuation is based on IPO-at-issue price bands. Peer multiples are based on current market data. 
          A negative premium indicates the target is priced below the peer median.
        </div>
      </div>
    </div>
  );
}
