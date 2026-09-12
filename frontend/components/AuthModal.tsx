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
    <div 
      className="fixed inset-0 bg-[#001428]/50 backdrop-blur-sm flex items-center justify-center z-50 p-4" 
      onClick={() => setAuthModalOpen(false)}
    >
      <div 
        className="bg-white border border-[#e2e8f0] rounded-[2px] shadow-2xl w-full max-w-sm p-6 relative" 
        onClick={(e) => e.stopPropagation()}
      >
        <button 
          className="absolute top-4 right-4 text-[#64748b] hover:text-[#001428] p-1 rounded-[2px] hover:bg-[#f1f5f9] transition-colors" 
          onClick={() => setAuthModalOpen(false)}
          aria-label="Close"
        >
          <X size={18} />
        </button>

        <h2 className="text-base font-bold text-[#001428] mb-1">
          {isLogin ? "Sign In to Terminal" : "Create Account"}
        </h2>
        <p className="text-xs text-[#64748b] mb-5">
          {isLogin
            ? "Access institutional valuation models and research sessions."
            : "Register to track filings and build custom watchlists."}
        </p>

        {error && (
          <div className="text-xs text-[#b91c1c] bg-[#fef2f2] border border-[#fecaca] p-2.5 rounded-[2px] mb-4 leading-relaxed">
            {error}
          </div>
        )}

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="block text-[11px] font-bold text-[#475569] uppercase tracking-wider mb-1.5">
              Email Address
            </label>
            <input
              type="email"
              className="w-full h-9 px-3 text-xs bg-white border border-[#cbd5e1] rounded-[2px] text-[#0f172a] placeholder-[#94a3b8] focus:outline-none focus:border-[#001428] focus:ring-1 focus:ring-[#001428] transition-colors"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="analyst@firm.com"
              required
            />
          </div>
          
          <div>
            <label className="block text-[11px] font-bold text-[#475569] uppercase tracking-wider mb-1.5">
              Password
            </label>
            <input
              type="password"
              className="w-full h-9 px-3 text-xs bg-white border border-[#cbd5e1] rounded-[2px] text-[#0f172a] placeholder-[#94a3b8] focus:outline-none focus:border-[#001428] focus:ring-1 focus:ring-[#001428] transition-colors"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button 
            type="submit" 
            className="w-full h-9 bg-[#001428] hover:bg-[#0f2942] text-white text-xs font-semibold rounded-[2px] transition-colors mt-2 disabled:opacity-60"
            disabled={loading}
          >
            {loading ? "Authenticating..." : (isLogin ? "Sign In" : "Create Account")}
          </button>
        </form>

        <div className="mt-5 text-center text-xs text-[#64748b] pt-4 border-t border-[#f1f5f9]">
          {isLogin ? "Don't have an account?" : "Already registered?"}
          <button 
            type="button" 
            className="text-[#0f2942] font-semibold hover:underline ml-1.5 transition-colors"
            onClick={() => { setIsLogin(!isLogin); setError(""); }}
          >
            {isLogin ? "Create one" : "Sign in"}
          </button>
        </div>
      </div>
    </div>
  );
}
