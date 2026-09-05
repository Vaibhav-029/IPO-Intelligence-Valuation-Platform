import { Inter } from "next/font/google";
import "./globals.css";
import Navbar from "../components/Navbar";
import { AuthProvider } from "../lib/AuthContext";
import AuthModal from "../components/AuthModal";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = { title: "IPO Intelligence", description: "Source-backed IPO research and valuation" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { 
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <AuthProvider>
          <Navbar />
          <AuthModal />
          {children}
        </AuthProvider>
      </body>
    </html>
  ); 
}
