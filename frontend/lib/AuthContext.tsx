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
    // Check if we saved a user in localStorage
    const savedEmail = localStorage.getItem("user_email");
    const token = localStorage.getItem("access_token");
    
    if (savedEmail && token) {
      setUser({ email: savedEmail });
      setAccessToken(token);
    } else {
      // Even if we don't have an access token, we might have a refresh cookie.
      // A robust app would try to call /auth/refresh here to hydrate the session.
      // For simplicity, we'll try to refresh silently on mount.
      apiFetch("/auth/refresh", { method: "POST" })
        .then((data) => {
          if (data && data.access_token) {
            setAccessToken(data.access_token);
            // Decode JWT payload to get email (or call a /me endpoint)
            // JWT payload has "sub" (id) and typically "email" depending on our implementation.
            // Our backend encodes user sub and type. Email is not in the token. 
            // A small limitation without a `/me` endpoint, so we fallback to a placeholder if needed.
            // Ideally backend would have /api/v1/auth/me. 
            setUser({ email: "user@ipointelligence.com" }); 
            localStorage.setItem("access_token", data.access_token);
          }
        })
        .catch(() => {
          // Normal if not logged in
        })
        .finally(() => {
          setLoading(false);
        });
        return;
    }
    setLoading(false);
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
