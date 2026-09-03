"use client";

import React, { useState, useEffect } from "react";
import { apiFetch } from "../lib/api";
import { Calculator } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

type DCFCalculatorProps = {
  initialRevenue?: number;
  initialMargin?: number;
};

type Projection = {
  year: number;
  revenue: number;
  ebitda: number;
  d_and_a: number;
  ebit: number;
  taxes: number;
  capex: number;
  change_in_nwc: number;
  fcff: number;
  present_value: number;
};

type DCFResponse = {
  inputs: {
    historical: {
      base_revenue: number;
      debt: number | null;
      cash: number | null;
      post_issue_shares: number | null;
    };
    assumptions: any;
  };
  projections: Projection[];
  valuation: {
    enterprise_value: number;
    terminal_value: number;
    terminal_value_pv: number;
    equity_value: number | null;
    intrinsic_value_per_share: number | null;
    implied_upside_pct_lower_band: number | null;
    implied_upside_pct_upper_band: number | null;
  };
  sensitivity: {
    wacc_values: number[];
    terminal_growth_values: number[];
    grid: (number | null)[][];
  };
};

export default function DCFCalculator({ initialRevenue = 1000, initialMargin = 0.20 }: DCFCalculatorProps) {
  // We no longer use initialRevenue since base_revenue comes from the backend automatically, 
  // but we can still pass it as default fallback for the first render.
  const [margin, setMargin] = useState(initialMargin * 100);
  const [growth, setGrowth] = useState(15);
  const [discount, setDiscount] = useState(12);
  const [terminal, setTerminal] = useState(5);
  const [tax, setTax] = useState(25);
  const [years, setYears] = useState(5);
  const [daPct, setDaPct] = useState(5);
  const [capexPct, setCapexPct] = useState(6);
  const [nwcPct, setNwcPct] = useState(10);

  const [result, setResult] = useState<DCFResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (initialMargin > 0) setMargin(initialMargin);
  }, [initialMargin]);

  // We need to parse ipo_id from the URL to hit the new endpoint
  const [ipoId, setIpoId] = useState<number | null>(null);
  useEffect(() => {
    const match = window.location.pathname.match(/\/ipos\/(\d+)/);
    if (match) setIpoId(Number(match[1]));
  }, []);

  useEffect(() => {
    if (!ipoId) return;

    const fetchDCF = async () => {
      setLoading(true);
      setError("");
      try {
        const payload = {
          revenue_growth_rate: growth / 100,
          ebitda_margin: margin / 100,
          tax_rate: tax / 100,
          d_and_a_pct_of_revenue: daPct / 100,
          capex_pct_of_revenue: capexPct / 100,
          change_in_nwc_pct_of_revenue: nwcPct / 100,
          discount_rate: discount / 100,
          terminal_growth_rate: terminal / 100,
          years
        };
        const res = await apiFetch(`/ipos/${ipoId}/dcf`, {
          method: "POST",
          body: JSON.stringify(payload)
        });
        setResult(res);
      } catch (e: any) {
        setError(typeof e.message === 'string' ? e.message : JSON.stringify(e.message));
      } finally {
        setLoading(false);
      }
    };

    const timer = setTimeout(fetchDCF, 300);
    return () => clearTimeout(timer);
  }, [ipoId, margin, growth, discount, terminal, tax, daPct, capexPct, nwcPct, years]);

  const chartData = result?.projections?.map((cf: any) => ({
    name: `Year ${cf.year}`,
    "fcff": cf.fcff,
    "present_value": cf.present_value,
  })) || [];

  return (
    <div className="panel glass-panel" style={{ gridColumn: "1 / -1", marginTop: "var(--space-xl)", animation: "fadeInUp 0.7s ease-out" }}>
      <div className="section-title">
        <h2 style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Calculator color="var(--cyan)" size={20}/> DCF Calculator
        </h2>
        <span className="chip">Interactive</span>
      </div>
      
      <div style={{ display: "flex", gap: "32px", flexWrap: "wrap", marginTop: "24px" }}>
        
        {/* Left Col: Controls */}
        <div style={{ flex: "1 1 300px", display: "flex", flexDirection: "column", gap: 20 }}>
          
          <div>
            <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span>EBITDA Margin</span>
              <span>{margin.toFixed(1)}%</span>
            </label>
            <input type="range" min="0" max="100" step="0.5" value={margin} onChange={e => setMargin(Number(e.target.value))} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span>Revenue Growth</span>
              <span>{growth.toFixed(1)}%</span>
            </label>
            <input type="range" min="-20" max="100" step="1" value={growth} onChange={e => setGrowth(Number(e.target.value))} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span>Discount Rate (WACC)</span>
              <span>{discount.toFixed(1)}%</span>
            </label>
            <input type="range" min="5" max="30" step="0.5" value={discount} onChange={e => setDiscount(Number(e.target.value))} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span>Terminal Growth</span>
              <span>{terminal.toFixed(1)}%</span>
            </label>
            <input type="range" min="0" max={discount - 0.5} step="0.5" value={terminal} onChange={e => setTerminal(Number(e.target.value))} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span>D&A (% of Rev)</span>
              <span>{daPct.toFixed(1)}%</span>
            </label>
            <input type="range" min="0" max="20" step="0.5" value={daPct} onChange={e => setDaPct(Number(e.target.value))} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span>CapEx (% of Rev)</span>
              <span>{capexPct.toFixed(1)}%</span>
            </label>
            <input type="range" min="0" max="30" step="0.5" value={capexPct} onChange={e => setCapexPct(Number(e.target.value))} style={{ width: "100%" }} />
          </div>
          <div>
            <label style={{ display: "flex", justifyContent: "space-between", fontSize: 13, marginBottom: 8 }}>
              <span>Change in NWC (% of Rev)</span>
              <span>{nwcPct.toFixed(1)}%</span>
            </label>
            <input type="range" min="-20" max="30" step="0.5" value={nwcPct} onChange={e => setNwcPct(Number(e.target.value))} style={{ width: "100%" }} />
          </div>

        </div>

        {/* Right Col: Output */}
        <div style={{ flex: "2 1 400px", display: "flex", flexDirection: "column", gap: 20 }}>
          
          <div style={{ background: "rgba(0, 255, 204, 0.05)", border: "1px solid rgba(0, 255, 204, 0.2)", borderRadius: 12, padding: 24, textAlign: "center" }}>
            <div style={{ fontSize: 14, color: "var(--muted)", marginBottom: 8 }}>Implied Enterprise Value</div>
            {error ? (
              <div style={{ color: "var(--red)" }}>{error}</div>
            ) : (
              <div style={{ fontSize: 36, fontWeight: 700, color: "var(--cyan)" }}>
                ₹{result?.valuation?.enterprise_value?.toLocaleString() ?? "—"} <span style={{ fontSize: 16, fontWeight: 400, color: "var(--muted)" }}>Cr</span>
              </div>
            )}
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 12 }}>
              Terminal Value contributes ₹{result?.valuation?.terminal_value_pv?.toLocaleString() ?? "—"} Cr (PV)
            </div>
            {result?.valuation?.intrinsic_value_per_share !== null && result?.valuation?.intrinsic_value_per_share !== undefined && (
              <div style={{ fontSize: 16, color: "var(--ink)", marginTop: 16 }}>
                Intrinsic Value per Share: <b>₹{result.valuation.intrinsic_value_per_share.toLocaleString()}</b>
              </div>
            )}
          </div>

          <div style={{ height: 200, width: "100%" }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 10, right: 0, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                <XAxis dataKey="name" tick={{ fill: "#8f9bb3", fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: "#8f9bb3", fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={v => `₹${v}`} width={48} />
                <Tooltip 
                  contentStyle={{ background: "rgba(12, 22, 38, 0.95)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 8, color: "#fff" }}
                  itemStyle={{ color: "var(--cyan)", fontWeight: 600 }}
                  formatter={(value: any) => [`₹${Number(value).toFixed(0)} Cr`, undefined]}
                />
                <Bar dataKey="fcff" name="Free Cash Flow" fill="rgba(68, 215, 209, 0.2)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="present_value" name="Present Value" fill="var(--cyan)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

        </div>
      </div>
      
      {result?.sensitivity && (
        <div style={{ marginTop: 40 }}>
          <h3 style={{ fontSize: 14, color: "var(--muted)", marginBottom: 12 }}>Sensitivity Analysis (Intrinsic Value / Share)</h3>
          <div style={{ overflowX: "auto" }}>
            <table className="table" style={{ fontSize: 13, textAlign: "center", width: "100%" }}>
              <thead>
                <tr>
                  <th style={{ textAlign: "left" }}>WACC \ Term Growth</th>
                  {result.sensitivity.terminal_growth_values.map(tg => <th key={tg}>{tg}%</th>)}
                </tr>
              </thead>
              <tbody>
                {result.sensitivity.wacc_values.map((w, rIdx) => (
                  <tr key={w}>
                    <td style={{ textAlign: "left", fontWeight: 600, color: "var(--muted)" }}>{w}%</td>
                    {result.sensitivity.grid[rIdx].map((cell, cIdx) => (
                      <td key={cIdx} style={{ color: cell ? "var(--ink)" : "var(--dimmed)" }}>
                        {cell ? `₹${cell.toLocaleString()}` : "N/A"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

    </div>
  );
}
