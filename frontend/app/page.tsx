"use client";
import { useEffect, useMemo, useState } from "react";
import { Search, Sparkles } from "lucide-react";
import { getIPOs, IPO } from "../lib/api";
import IPOCard from "../components/IPOCard";
import Shimmer from "../components/Shimmer";

export default function Directory() {
  const [ipos, setIpos] = useState<IPO[]>([]); 
  const [query, setQuery] = useState(""); 
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => { 
    getIPOs()
      .then(data => { setIpos(data); setLoading(false); })
      .catch(() => { setError("Start the API to load the curated IPO directory."); setLoading(false); }); 
  }, []);

  const filtered = useMemo(() => 
    ipos.filter(x => `${x.name} ${x.sector}`.toLowerCase().includes(query.toLowerCase())), 
    [ipos, query]
  );

  return (
    <main style={{ animation: "fadeIn 0.5s ease-out" }}>
      <section className="hero">
        <div>
          <div className="eyebrow">India IPO research terminal</div>
          <h1>Know the numbers.<br/><span style={{color:"var(--cyan)"}}>Interrogate the evidence.</span></h1>
          <p>Source-grounded filing intelligence, deterministic valuation, peer context and an AI research workflow designed to explain—not invent—financial truth.</p>
        </div>
        <div className="stat-row">
          <div className="stat"><b>{ipos.length > 0 ? ipos.length : "..."}</b><span>Curated IPOs</span></div>
          <div className="stat"><b>5+</b><span>Research tools</span></div>
          <div className="stat"><b>v1.0</b><span>Scoring method</span></div>
        </div>
      </section>
      
      <div className="section-title">
        <div>
          <div className="eyebrow">Research universe</div>
          <h2>IPO Directory</h2>
        </div>
      </div>
      
      <div className="toolbar" style={{marginTop:16}}>
        <Search size={18} color="#8f9bb3"/>
        <input className="search" value={query} onChange={e=>setQuery(e.target.value)} placeholder="Search company or sector"/>
      </div>
      
      {error && <p>{error}</p>}
      
      {loading ? (
        <Shimmer />
      ) : (
        <div className="grid">
          {filtered.map((ipo, i) => (
            <IPOCard key={ipo.id} ipo={ipo} index={i} />
          ))}
        </div>
      )}
      
      {!loading && !error && filtered.length === 0 && (
        <p style={{ marginTop: 40, color: "var(--dimmed)" }}>No companies match your search.</p>
      )}
      
      <div className="panel" style={{marginTop: 48, display:"flex", justifyContent:"space-between", gap:20, alignItems:"center"}}>
        <div>
          <div className="eyebrow">Built for verifiability</div>
          <h2 style={{marginTop:6}}>Every calculation is deterministic.</h2>
          <p style={{marginBottom:0}}>The research layer combines structured metrics with filing-page evidence and discloses its confidence.</p>
        </div>
        <Sparkles color="var(--gold)" size={48} style={{ opacity: 0.8 }}/>
      </div>
    </main>
  );
}
