export const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export type IPO = {
  id: number;
  name: string;
  slug: string;
  sector: string;
  exchange?: string;
  status: string;
  issue_size_crore: number;
  price_band: [number, number];
  issue_date?: string;
  score?: number;
  description?: string;
  listing_segment?: string | null;
  logo_url?: string | null;
};

// Global token storage for the frontend
let currentAccessToken: string | null = null;

export function setAccessToken(token: string | null) {
  currentAccessToken = token;
  if (typeof window !== "undefined") {
    try {
      if (token) {
        localStorage.setItem("access_token", token);
      } else {
        localStorage.removeItem("access_token");
      }
    } catch (e) {
      console.warn("localStorage write error:", e);
    }
  }
}

export function getAccessToken(): string | null {
  if (currentAccessToken) return currentAccessToken;
  if (typeof window !== "undefined") {
    try {
      const stored = localStorage.getItem("access_token");
      if (stored) {
        currentAccessToken = stored;
        return stored;
      }
    } catch (e) {
      console.warn("localStorage access error:", e);
    }
  }
  return null;
}

export async function getIPOs(statusFilter?: string): Promise<IPO[]> {
  const url = statusFilter ? `${apiUrl}/ipos?status_filter=${encodeURIComponent(statusFilter)}` : `${apiUrl}/ipos`;
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("API unavailable");
  return (await response.json()).items;
}

export async function getIPO(id: number) {
  const r = await fetch(`${apiUrl}/ipos/${id}`, { cache: "no-store" });
  if (!r.ok) throw new Error("IPO unavailable");
  return r.json();
}

export async function apiFetch(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  // Attach token if we have one
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const reqOptions = { ...options, headers };

  // Note: credentials "include" is required so the browser sends the httpOnly refresh_token cookie
  if (!reqOptions.credentials) {
    reqOptions.credentials = "include";
  }

  let r = await fetch(`${apiUrl}${path}`, reqOptions);

  // If 401, attempt to refresh the token automatically
  if (r.status === 401) {
    try {
      const refreshReq = await fetch(`${apiUrl}/auth/refresh`, {
        method: "POST",
        credentials: "include"
      });

      if (refreshReq.ok) {
        const { access_token } = await refreshReq.json();
        setAccessToken(access_token);

        // Retry original request with new token
        headers.set("Authorization", `Bearer ${access_token}`);
        r = await fetch(`${apiUrl}${path}`, { ...options, headers });
      } else {
        // Refresh failed, clear token so user is logged out
        setAccessToken(null);
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("user_email");
        }
      }
    } catch (e) {
      setAccessToken(null);
      if (typeof window !== "undefined") {
        localStorage.removeItem("access_token");
        localStorage.removeItem("user_email");
      }
    }
  }

  if (!r.ok) {
    const errData = await r.json().catch(() => ({ detail: "Request failed" }));
    let detail = errData.detail || "Request failed";
    if (typeof detail !== "string") detail = JSON.stringify(detail);
    throw new Error(detail);
  }

  // 204 No Content won't have a JSON body
  if (r.status === 204) return null;
  return r.json();
}

export interface ResearchSessionItem {
  id: number;
  ipo_id: number;
  title: string;
  created_at: string;
}

export interface ResearchCitation {
  document_id: number;
  page?: number;
  section?: string;
  excerpt: string;
}

export interface ResearchClaim {
  text: string;
  citations: ResearchCitation[];
}

export interface ResearchMessageItem {
  role: "user" | "assistant";
  content: string;
  tool_trace?: string[];
  citations?: ResearchClaim[];
  created_at: string;
}

export interface ResearchSessionDetail {
  id: number;
  ipo_id: number;
  title: string;
  messages: ResearchMessageItem[];
}

export interface ResearchResponse {
  answer: string;
  key_metrics?: {
    company?: string;
    sector?: string;
    issue_size_crore?: number;
    latest_revenue_crore?: number;
    latest_pat_crore?: number;
    revenue_cagr_2y?: number;
    ebitda_margin?: number;
    pe?: number;
    ps?: number;
  };
  claims?: ResearchClaim[];
  confidence?: string;
  tool_trace?: string[];
  mode?: string;
  disclaimer?: string;
}

export async function getResearchSessions(): Promise<ResearchSessionItem[]> {
  return apiFetch("/research/sessions");
}

export async function getResearchSession(sessionId: number): Promise<ResearchSessionDetail> {
  return apiFetch(`/research/sessions/${sessionId}`);
}

export async function createResearchSession(ipoId: number, title?: string): Promise<{ id: number; ipo_id: number; title: string; created_at: string }> {
  return apiFetch("/research/sessions", {
    method: "POST",
    body: JSON.stringify({ ipo_id: ipoId, title: title || "IPO research" })
  });
}

export async function sendResearchMessage(sessionId: number, content: string): Promise<ResearchResponse> {
  return apiFetch(`/research/sessions/${sessionId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export async function deleteResearchSession(sessionId: number): Promise<void> {
  return apiFetch(`/research/sessions/${sessionId}`, {
    method: "DELETE"
  });
}

export interface WatchlistItem {
  watchlist_id: number;
  ipo_id: number;
  name: string;
  slug: string;
  sector: string;
  status: string;
  listing_segment: string;
  exchange: string;
  score?: number | null;
  issue_size_crore?: number | null;
  price_band?: [number, number];
  open_date?: string | null;
  close_date?: string | null;
  listing_date?: string | null;
  saved_at?: string;
  logo_url?: string | null;
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  return apiFetch("/watchlist");
}

export async function addToWatchlist(ipoId: number): Promise<{ id: number; ipo_id: number; created: boolean }> {
  return apiFetch("/watchlist", {
    method: "POST",
    body: JSON.stringify({ ipo_id: ipoId }),
  });
}

export async function removeFromWatchlist(itemIdOrIpoId: number): Promise<void> {
  return apiFetch(`/watchlist/${itemIdOrIpoId}`, {
    method: "DELETE",
  });
}

