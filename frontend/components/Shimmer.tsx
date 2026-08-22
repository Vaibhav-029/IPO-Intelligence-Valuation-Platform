import React from "react";

export default function Shimmer() {
  return (
    <div className="grid">
      {[...Array(6)].map((_, i) => (
        <div key={i} className="shimmer-card">
          <div style={{ padding: 24, animation: "shimmer 2s infinite linear", backgroundImage: "linear-gradient(90deg, rgba(28, 45, 71, 0.4) 0%, rgba(28, 45, 71, 0.8) 50%, rgba(28, 45, 71, 0.4) 100%)", backgroundSize: "200% 100%", height: "100%", borderRadius: 12 }}>
             <div className="shimmer-line short" style={{ background: "rgba(255,255,255,0.05)" }}></div>
             <div className="shimmer-line medium" style={{ background: "rgba(255,255,255,0.05)", marginTop: 20 }}></div>
             <div className="shimmer-line" style={{ background: "rgba(255,255,255,0.05)" }}></div>
          </div>
        </div>
      ))}
    </div>
  );
}
