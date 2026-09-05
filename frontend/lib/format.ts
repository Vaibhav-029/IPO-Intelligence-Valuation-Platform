export function date(value: string | undefined | null): string {
  if (!value) return "—";
  try {
    const d = new Date(value);
    if (isNaN(d.getTime())) return value;
    return d.toLocaleDateString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch (e) {
    return value;
  }
}

export function priceBand(band: [number, number] | undefined | null): string {
  if (!band || !Array.isArray(band) || band.length !== 2) return "—";
  const [low, high] = band;
  if (!low && !high) return "—";
  if (low === 0 && high === 0) return "—";
  if (low === high || !high) return `₹${low.toLocaleString("en-IN")}`;
  if (!low && high) return `₹${high.toLocaleString("en-IN")}`;
  return `₹${low.toLocaleString("en-IN")} – ₹${high.toLocaleString("en-IN")}`;
}

export function issueSize(crores: number | undefined | null): string {
  if (crores === null || crores === undefined || isNaN(crores) || crores === 0) return "—";
  return `₹${crores.toLocaleString("en-IN", { maximumFractionDigits: 1 })} Cr`;
}

export function scoreOutOfTen(score: number | undefined | null): string {
  if (score === null || score === undefined || isNaN(score)) return "—";
  return `${(score / 10).toFixed(1)} / 10`;
}

