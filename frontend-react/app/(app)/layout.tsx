"use client";

import { Sidebar } from "@/components/Sidebar";
import { ThemeToggle } from "@/components/ThemeToggle";
import { logout } from "@/lib/api";
import { LogOut, Menu } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [clock, setClock] = useState("");

  useEffect(() => {
    const tick = () =>
      setClock(
        new Date().toLocaleTimeString("en-US", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
          second: "2-digit",
        })
      );
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, []);

  const handleLogout = async () => {
    await logout().catch(() => null);
    // Clear in-memory chat so the next user starts fresh
    const { chatStore } = await import("@/lib/chatStore");
    chatStore.clearChat();
    router.push("/login");
  };

  // Sidebar width: 220px open, 56px collapsed
  const sidebarW = sidebarOpen ? 220 : 56;

  return (
    <div className="h-screen flex bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* ── Sidebar ──────────────────────────────── */}
      <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen((v) => !v)} />

      {/* ── Main content area — offset by sidebar ─ */}
      <div
        className="flex flex-col flex-1 overflow-hidden transition-all duration-300"
        style={{ marginLeft: sidebarW }}
      >
        {/* Top bar */}
        <header className="flex items-center gap-4 px-5 py-2.5 border-b border-zinc-800 bg-zinc-950 shrink-0">
          {/* Hamburger — only shown when sidebar is collapsed */}
          {!sidebarOpen && (
            <button
              onClick={() => setSidebarOpen(true)}
              className="flex items-center justify-center w-7 h-7 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-200 transition-colors shrink-0"
              aria-label="Expand sidebar"
            >
              <Menu className="w-4 h-4" />
            </button>
          )}

          {/* Spacer pushes everything else right */}
          <div className="flex-1" />

          {/* Live dot */}
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            LIVE
          </div>

          {/* Clock */}
          <span className="font-mono text-xs text-zinc-500 tabular-nums">{clock}</span>

          {/* Theme toggle */}
          <ThemeToggle />

          {/* Logout */}
          <button
            onClick={handleLogout}
            className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-500/10"
          >
            <LogOut className="w-3.5 h-3.5" />
            Logout
          </button>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto scrollbar-thin">
          {children}
        </main>
      </div>
    </div>
  );
}
