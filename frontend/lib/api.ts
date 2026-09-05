export const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export type IPO = { 
  id:number; 
  name:string; 
  slug:string; 
  sector:string; 
  exchange?:string; 
  status:string; 
  issue_size_crore:number; 
  price_band:[number,number]; 
  issue_date?:string; 
  score?:number; 
  description?:string;
  listing_segment?:string | null;
  logo_url?:string | null;
};

// Global token storage for the frontend
let currentAccessToken: string | null = null;

export function setAccessToken(token: string | null) {
  currentAccessToken = token;
}

export function getAccessToken() {
  return currentAccessToken;
}

export async function getIPOs(statusFilter?: string): Promise<IPO[]> {
  const url = statusFilter ? `${apiUrl}/ipos?status_filter=${encodeURIComponent(statusFilter)}` : `${apiUrl}/ipos`;
  const response = await fetch(url, { cache: "no-store" });
  if (!response.ok) throw new Error("API unavailable");
  return (await response.json()).items;
}

export async function getIPO(id: number) { 
  const r = await fetch(`${apiUrl}/ipos/${id}`, {cache:"no-store"}); 
  if(!r.ok) throw new Error("IPO unavailable"); 
  return r.json(); 
}

export async function apiFetch(path: string, options: RequestInit = {}) { 
  const headers = new Headers(options.headers || {});
  headers.set("Content-Type", "application/json");

  // Attach token if we have one
  if (currentAccessToken) {
    headers.set("Authorization", `Bearer ${currentAccessToken}`);
  }

  const reqOptions = { ...options, headers };
  
  // Note: credentials "include" is required so the browser sends the httpOnly refresh_token cookie
  if (!reqOptions.credentials) {
    reqOptions.credentials = "include";
  }

  let r = await fetch(`${apiUrl}${path}`, reqOptions); 

  // If 401, attempt to refresh the token automatically
  if (r.status === 401 && currentAccessToken) {
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
      }
    } catch (e) {
      setAccessToken(null);
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
