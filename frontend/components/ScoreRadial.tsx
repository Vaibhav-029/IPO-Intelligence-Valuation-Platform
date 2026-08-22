import React from "react";

export default function ScoreRadial({ score }: { score: number }) {
  const radius = 18;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 10) * circumference;

  let color = "var(--green)";
  if (score < 5) color = "var(--red)";
  else if (score < 7) color = "var(--gold)";

  return (
    <div className="score-radial">
      <svg width="44" height="44" viewBox="0 0 44 44">
        <circle
          cx="22"
          cy="22"
          r={radius}
          fill="none"
          stroke="var(--line)"
          strokeWidth="4"
        />
        <circle
          cx="22"
          cy="22"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="4"
          strokeDasharray={circumference}
          strokeDashoffset={strokeDashoffset}
          strokeLinecap="round"
          style={{ transform: "rotate(-90deg)", transformOrigin: "50% 50%", transition: "stroke-dashoffset 1s ease-out" }}
        />
      </svg>
      <div className="score-value">{score.toFixed(1)}</div>
    </div>
  );
}
