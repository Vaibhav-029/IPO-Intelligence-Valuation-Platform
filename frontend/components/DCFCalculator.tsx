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

type CashFlow = {
  year: number;
  revenue: number;
  free_cash_flow: number;
  present_value: number;
};

type DCFResponse = {
  enterprise_value_crore: number;
  terminal_value_pv_crore: number;
  cashflows: CashFlow[];
  methodology: string;
};

export default function DCFCalculator({ initialRevenue = 1000, initialMargin = 0.20 }: DCFCalculatorProps) {
  const [revenue, setRevenue] = useState(initialRevenue);
  const [margin, setMargin] = useState(initialMargin * 100);
  const [growth, setGrowth] = useState(15);
  const [discount, setDiscount] = useState(12);
  const [terminal, setTerminal] = useState(5);
  const [tax, setTax] = useState(25);
  const [years, setYears] = useState(5);

  const [result, setResult] = useState<DCFResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    // Only update if it's > 0 (meaning we got actual data)
    if (initialRevenue > 0) setRevenue(initialRevenue);
    if (initialMargin > 0) setMargin(initialMargin);
  }, [initialRevenue, initialMargin]);

  useEffect(() => {
    const fetchDCF = async () => {
      setLoading(true);
      setError("");
      try {
        const payload = {
          revenue,
          ebitda_margin: margin / 100,
          tax_rate: tax / 100,
          growth_rate: growth / 100,
          discount_rate: discount / 100,
          terminal_growth: terminal / 100,
          years
        };
        const res = await apiFetch("/valuation/dcf", {
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

    // Debounce to prevent spam
    const timer = setTimeout(fetchDCF, 300);
    return () => clearTimeout(timer);
  }, [revenue, margin, growth, discount, terminal, tax, years]);

  const chartData = result?.cashflows.map(cf => ({
    name: `Year ${cf.year}`,
    "Free Cash Flow": cf.free_cash_flow,
    "Present Value": cf.present_value,
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
              <span>Base Revenue (Cr)</span>
              <span>₹{revenue.toLocaleString()}</span>
            </label>
            <input type="range" min="100" max={Math.max(10000, revenue * 2)} step="100" value={revenue} onChange={e => setRevenue(Number(e.target.value))} style={{ width: "100%" }} />
          </div>

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

        </div>

        {/* Right Col: Output */}
        <div style={{ flex: "2 1 400px", display: "flex", flexDirection: "column", gap: 20 }}>
          
          <div style={{ background: "rgba(0, 255, 204, 0.05)", border: "1px solid rgba(0, 255, 204, 0.2)", borderRadius: 12, padding: 24, textAlign: "center" }}>
            <div style={{ fontSize: 14, color: "var(--muted)", marginBottom: 8 }}>Implied Enterprise Value</div>
            {error ? (
              <div style={{ color: "var(--red)" }}>{error}</div>
            ) : (
              <div style={{ fontSize: 36, fontWeight: 700, color: "var(--cyan)" }}>
                ₹{result?.enterprise_value_crore?.toLocaleString() ?? "—"} <span style={{ fontSize: 16, fontWeight: 400, color: "var(--muted)" }}>Cr</span>
              </div>
            )}
            <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 12 }}>
              Terminal Value contributes ₹{result?.terminal_value_pv_crore?.toLocaleString() ?? "—"} Cr (PV)
            </div>
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
                <Bar dataKey="Free Cash Flow" fill="rgba(68, 215, 209, 0.2)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="Present Value" fill="var(--cyan)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

        </div>

      </div>
    </div>
  );
}
