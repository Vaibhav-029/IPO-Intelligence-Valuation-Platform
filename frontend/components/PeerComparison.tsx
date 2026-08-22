"use client";

import React, { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { Users } from "lucide-react";

type Any = Record<string, any>;

type PeerComparisonProps = {
  ipoId: number;
};

const n = (value: any, suffix = "") =>
  value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}${suffix}`;

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

  const summary = data.summary;
  const target = data.target;
  const peers = data.peers;

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
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>Mkt Cap (Cr)</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>P/E</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>P/S</th>
              <th style={{ padding: "12px 8px", fontWeight: 500 }}>EV/EBITDA</th>
            </tr>
          </thead>
          <tbody>
            {/* Target Company Row */}
            <tr style={{ backgroundColor: "rgba(0, 255, 204, 0.05)", borderBottom: "1px solid rgba(255,255,255,0.1)" }}>
              <td style={{ padding: "16px 8px", fontWeight: 600, color: "var(--cyan)" }}>
                {target?.name} (Target)
              </td>
              <td style={{ padding: "16px 8px" }}>{target?.market_cap ? `₹${Math.round(target.market_cap).toLocaleString()}` : "—"}</td>
              <td style={{ padding: "16px 8px" }}>{n(target?.pe, "x")}</td>
              <td style={{ padding: "16px 8px" }}>{n(target?.ps, "x")}</td>
              <td style={{ padding: "16px 8px" }}>{n(target?.ev_ebitda, "x")}</td>
            </tr>

            {/* Peer Rows */}
            {peers.map((peer: Any, idx: number) => (
              <tr key={idx} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                <td style={{ padding: "16px 8px" }}>{peer.name}</td>
                <td style={{ padding: "16px 8px", color: "var(--muted)" }}>{peer.market_cap ? `₹${Math.round(peer.market_cap).toLocaleString()}` : "—"}</td>
                <td style={{ padding: "16px 8px", color: "var(--ink)" }}>{n(peer.pe, "x")}</td>
                <td style={{ padding: "16px 8px", color: "var(--ink)" }}>{n(peer.ps, "x")}</td>
                <td style={{ padding: "16px 8px", color: "var(--ink)" }}>{n(peer.ev_ebitda, "x")}</td>
              </tr>
            ))}
            
            {/* Median Row */}
            <tr style={{ backgroundColor: "rgba(255,255,255,0.02)", fontStyle: "italic" }}>
              <td style={{ padding: "16px 8px", color: "var(--muted)" }}>Peer Median</td>
              <td colSpan={1} style={{ padding: "16px 8px" }}></td>
              <td style={{ padding: "16px 8px", color: "var(--muted)" }}>{n(summary?.peer_median_pe, "x")}</td>
              <td colSpan={2} style={{ padding: "16px 8px" }}></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div style={{ marginTop: 24, fontSize: 13, color: "var(--dimmed)" }}>
        Target P/E is trading at a {summary?.pe_premium_discount_pct > 0 ? "premium" : "discount"} of {Math.abs(summary?.pe_premium_discount_pct)}% compared to the peer median.
      </div>
    </div>
  );
}
