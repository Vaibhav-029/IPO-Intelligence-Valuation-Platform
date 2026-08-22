"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { useAuth } from "../lib/AuthContext";

export default function AuthModal() {
  const { isAuthModalOpen, setAuthModalOpen, login, register } = useAuth();
  
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isAuthModalOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    
    try {
      if (isLogin) {
        await login(email, password);
      } else {
        await register(email, password);
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={() => setAuthModalOpen(false)}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={() => setAuthModalOpen(false)}>
          <X size={20} />
        </button>

        <h2 className="modal-title">
          {isLogin ? "Sign in to continue" : "Create an account"}
        </h2>
        <p className="modal-desc">
          {isLogin
            ? "Access your saved research and watchlists."
            : "Join to save IPOs and analyze documents."}
        </p>

        {error && (
          <div style={{ color: "#ef4444", fontSize: 13, marginBottom: 16, background: "rgba(239, 68, 68, 0.1)", padding: "8px 12px", borderRadius: 6 }}>
            {error}
          </div>
        )}

        <form className="modal-form" onSubmit={handleSubmit}>
          <div>
            <label style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Email</label>
            <input
              type="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="name@example.com"
              required
            />
          </div>
          
          <div>
            <label style={{ display: "block", fontSize: 12, color: "var(--muted)", marginBottom: 4 }}>Password</label>
            <input
              type="password"
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button 
            type="submit" 
            className="button primary" 
            style={{ width: "100%", marginTop: 8 }}
            disabled={loading}
          >
            {loading ? "Please wait..." : (isLogin ? "Sign In" : "Create Account")}
          </button>
        </form>

        <div className="modal-footer">
          {isLogin ? "Don't have an account?" : "Already have an account?"}
          <button type="button" onClick={() => { setIsLogin(!isLogin); setError(""); }}>
            {isLogin ? "Sign up" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
