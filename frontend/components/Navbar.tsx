"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/AuthContext";
import { LogOut, User } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const { user, loading, logout, setAuthModalOpen } = useAuth();

  return (
    <nav className="nav">
      <Link className="brand" href="/">
        <span className="brand-mark">I</span> IPO Intelligence
      </Link>
      <div className="navlinks">
        <Link href="/" className={pathname === "/" ? "active" : ""}>Directory</Link>
        <span className={pathname.startsWith("/ipos") ? "active" : ""}>Research workspace</span>
        <span>Methodology v1.0</span>
      </div>
      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 16 }}>
        {!loading && (
          user ? (
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13, color: "var(--ink)" }}>
                <User size={14} color="var(--cyan)" />
                {user.email}
              </div>
              <button 
                onClick={logout} 
                style={{ background: "transparent", border: "none", color: "var(--muted)", cursor: "pointer", display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}
              >
                <LogOut size={14} /> Log out
              </button>
            </div>
          ) : (
            <button 
              className="button secondary" 
              onClick={() => setAuthModalOpen(true)}
              style={{ padding: "6px 14px", fontSize: 13 }}
            >
              Sign In
            </button>
          )
        )}
      </div>
    </nav>
  );
}
