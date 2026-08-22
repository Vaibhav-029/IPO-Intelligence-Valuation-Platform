import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { IPO } from "../lib/api";
import ScoreRadial from "./ScoreRadial";

export default function IPOCard({ ipo, index }: { ipo: IPO, index: number }) {
  return (
    <Link 
      href={`/ipos/${ipo.id}`} 
      className="card"
      style={{ animationDelay: `${index * 0.05}s` }}
    >
      <div className="card-top">
        <span className="sector">{ipo.sector}</span>
        {ipo.score ? <ScoreRadial score={ipo.score} /> : null}
      </div>
      
      <h2>{ipo.name}</h2>
      
      <div className="status-badge" style={{ marginTop: 8, marginBottom: 16 }}>
        <span className={`badge-dot ${ipo.status.toLowerCase()}`}></span>
        {ipo.status} · {ipo.exchange || "NSE / BSE"}
      </div>
      
      <div className="price">₹{ipo.price_band[0]}–{ipo.price_band[1]}</div>
      <div className="label">Price band · Issue size ₹{ipo.issue_size_crore} Cr</div>
      
      <div className="metric-row action-row">
        Open research <ArrowUpRight size={16} />
      </div>
    </Link>
  );
}
