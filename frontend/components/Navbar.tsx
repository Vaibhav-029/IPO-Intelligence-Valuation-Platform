"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "../lib/AuthContext";
import { LogOut, User, Search } from "lucide-react";

export default function Navbar() {
  const pathname = usePathname();
  const { user, loading, logout, setAuthModalOpen } = useAuth();

  return (
    <header className="navbar-wrapper">
      <div className="navbar-inner">
        <div className="nav-brand-group">
          <Link className="brand-wordmark" href="/">
            <span className="brand-text">IPO Intelligence</span>
          </Link>
          <nav className="navlinks">
            <Link href="/" className={`navlink ${pathname === "/" ? "active" : ""}`}>
              Market
            </Link>
            <Link href="/research" className={`navlink ${pathname.startsWith("/research") ? "active" : ""}`}>
              Research
            </Link>
            <Link href="/watchlist" className={`navlink ${pathname.startsWith("/watchlist") ? "active" : ""}`}>
              Watchlist
            </Link>
          </nav>
        </div>

        <div className="nav-actions">
          <div className="search-bar">
            <Search size={14} className="search-icon" />
            <input 
              type="text" 
              className="search-input" 
              placeholder="Search companies, sectors, DRHP..." 
              readOnly 
            />
            <div className="kbd-shortcut">
              <kbd>⌘</kbd>
              <kbd>K</kbd>
            </div>
          </div>

          <div className="nav-divider" />

          {!loading && (
            user ? (
              <div className="user-profile">
                <div className="user-info">
                  <User size={13} className="user-icon" />
                  <span className="user-email">{user.email}</span>
                </div>
                <button onClick={logout} className="logout-btn" title="Log out">
                  <LogOut size={13} />
                  <span>Log out</span>
                </button>
              </div>
            ) : (
              <button 
                className="btn-signin" 
                onClick={() => setAuthModalOpen(true)}
              >
                Sign In
              </button>
            )
          )}
        </div>
      </div>
    </header>
  );
}
