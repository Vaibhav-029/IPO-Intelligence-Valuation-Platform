"use client";
import React from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  BarChart,
  Bar,
} from "recharts";

type FinancialItem = {
  fiscal_year: string;
  revenue: number | null;
  ebitda: number | null;
  pat: number | null;
  ebitda_margin: number | null;
  pat_margin?: number | null;
};

type Props = {
  items: FinancialItem[];
};

const COLORS = {
  revenue: "#44d7d1",    // cyan
  ebitda: "#79a9ff",     // blue
  pat: "#f7c76a",        // gold
  margin: "#4ade80",     // green
};

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(12, 22, 38, 0.95)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: 10,
      padding: "14px 18px",
      fontSize: 13,
      backdropFilter: "blur(12px)",
      boxShadow: "0 8px 32px rgba(0,0,0,0.3)",
    }}>
      <div style={{ fontWeight: 700, marginBottom: 10, color: "#e8eefb" }}>{label}</div>
      {payload.map((entry: any) => (
        <div key={entry.name} style={{ display: "flex", justifyContent: "space-between", gap: 24, marginBottom: 4 }}>
          <span style={{ color: entry.color, fontWeight: 600 }}>{entry.name}</span>
          <span style={{ color: "#e8eefb" }}>
            {entry.name.includes("Margin") ? `${entry.value?.toFixed(1)}%` : `₹${entry.value?.toFixed(0)} Cr`}
          </span>
        </div>
      ))}
    </div>
  );
}

export default function FinancialChart({ items }: Props) {
  if (!items || items.length === 0) return null;

  // Prepare chart data — ensure numbers are clean
  const chartData = items.map((item) => ({
    name: item.fiscal_year,
    Revenue: item.revenue ?? 0,
    EBITDA: item.ebitda ?? 0,
    PAT: item.pat ?? 0,
    "EBITDA Margin": item.ebitda_margin ?? 0,
  }));

  return (
    <div className="chart-container">
      {/* Revenue / EBITDA / PAT area chart */}
      <div className="chart-section">
        <div className="chart-header">
          <h3>Revenue · EBITDA · PAT</h3>
          <span className="chip">INR crore</span>
        </div>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="gradRevenue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.revenue} stopOpacity={0.3} />
                <stop offset="100%" stopColor={COLORS.revenue} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradEBITDA" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.ebitda} stopOpacity={0.2} />
                <stop offset="100%" stopColor={COLORS.ebitda} stopOpacity={0} />
              </linearGradient>
              <linearGradient id="gradPAT" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.pat} stopOpacity={0.2} />
                <stop offset="100%" stopColor={COLORS.pat} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="name"
              tick={{ fill: "#8f9bb3", fontSize: 12 }}
              axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#8f9bb3", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}K` : `${v}`}
              width={48}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 12, color: "#8f9bb3", paddingTop: 12 }}
              iconType="circle"
              iconSize={8}
            />
            <Area
              type="monotone"
              dataKey="Revenue"
              stroke={COLORS.revenue}
              strokeWidth={2.5}
              fill="url(#gradRevenue)"
              dot={{ r: 4, fill: COLORS.revenue, strokeWidth: 0 }}
              activeDot={{ r: 6, strokeWidth: 2, stroke: "#0b1424" }}
            />
            <Area
              type="monotone"
              dataKey="EBITDA"
              stroke={COLORS.ebitda}
              strokeWidth={2}
              fill="url(#gradEBITDA)"
              dot={{ r: 3, fill: COLORS.ebitda, strokeWidth: 0 }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "#0b1424" }}
            />
            <Area
              type="monotone"
              dataKey="PAT"
              stroke={COLORS.pat}
              strokeWidth={2}
              fill="url(#gradPAT)"
              dot={{ r: 3, fill: COLORS.pat, strokeWidth: 0 }}
              activeDot={{ r: 5, strokeWidth: 2, stroke: "#0b1424" }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Margin bar chart */}
      <div className="chart-section">
        <div className="chart-header">
          <h3>EBITDA Margin</h3>
          <span className="chip">%</span>
        </div>
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis
              dataKey="name"
              tick={{ fill: "#8f9bb3", fontSize: 12 }}
              axisLine={{ stroke: "rgba(255,255,255,0.06)" }}
              tickLine={false}
            />
            <YAxis
              tick={{ fill: "#8f9bb3", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
              width={48}
              domain={[0, "auto"]}
            />
            <Tooltip content={<CustomTooltip />} />
            <Bar
              dataKey="EBITDA Margin"
              fill={COLORS.margin}
              radius={[6, 6, 0, 0]}
              barSize={36}
              opacity={0.85}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
