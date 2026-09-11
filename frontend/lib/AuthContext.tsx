"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { apiFetch, setAccessToken } from "./api";

type User = {
  email: string;
};

type AuthContextType = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  isAuthModalOpen: boolean;
  setAuthModalOpen: (open: boolean) => void;
};

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [isAuthModalOpen, setAuthModalOpen] = useState(false);

  // Initialize session on mount
  useEffect(() => {
    const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
    const savedEmail = typeof window !== "undefined" ? localStorage.getItem("user_email") : null;
    
    if (token) {
      setAccessToken(token);
      apiFetch("/auth/me")
        .then((data) => {
          if (data && data.authenticated) {
            setUser({ email: data.email || savedEmail || "user@ipointelligence.com" });
            if (data.email) localStorage.setItem("user_email", data.email);
          } else {
            setUser(null);
            setAccessToken(null);
          }
        })
        .catch(() => {
          // Token may be expired, try refresh
          apiFetch("/auth/refresh", { method: "POST" })
            .then((refData) => {
              if (refData && refData.access_token) {
                setAccessToken(refData.access_token);
                return apiFetch("/auth/me").then((meData) => {
                  setUser({ email: meData.email });
                  localStorage.setItem("user_email", meData.email);
                });
              } else {
                setUser(null);
                setAccessToken(null);
              }
            })
            .catch(() => {
              setUser(null);
              setAccessToken(null);
            })
            .finally(() => setLoading(false));
          return;
        })
        .finally(() => setLoading(false));
      return;
    }

    // No access token in localStorage, try refresh cookie
    apiFetch("/auth/refresh", { method: "POST" })
      .then((refData) => {
        if (refData && refData.access_token) {
          setAccessToken(refData.access_token);
          apiFetch("/auth/me")
            .then((meData) => {
              setUser({ email: meData.email });
              localStorage.setItem("user_email", meData.email);
            })
            .catch(() => {
              setUser({ email: savedEmail || "user@ipointelligence.com" });
            });
        } else {
          setUser(null);
        }
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = async (email: string, password: string) => {
    const data = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("user_email", email);
    setUser({ email });
    setAuthModalOpen(false);
  };

  const register = async (email: string, password: string) => {
    const data = await apiFetch("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("user_email", email);
    setUser({ email });
    setAuthModalOpen(false);
  };

  const logout = async () => {
    try {
      await apiFetch("/auth/logout", { method: "POST" });
    } catch (e) {
      console.error("Logout failed:", e);
    }
    setAccessToken(null);
    localStorage.removeItem("access_token");
    localStorage.removeItem("user_email");
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, logout, isAuthModalOpen, setAuthModalOpen }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
