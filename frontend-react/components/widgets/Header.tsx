"use client";

import { logout } from "@/lib/api";
import { LogOut, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function Header() {
  const router = useRouter();
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
    router.push("/login");
  };

  return (
    <header className="flex items-center justify-between px-6 py-3 border-b border-zinc-800 bg-zinc-950 shrink-0">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="p-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
          <Shield className="w-5 h-5 text-emerald-400" />
        </div>
        <div>
          <span
            className="text-sm font-bold tracking-widest uppercase text-zinc-100"
            style={{ fontFamily: "var(--font-serif)" }}
          >
            Firewall LLM
          </span>
          <span className="hidden sm:inline text-zinc-600 text-xs ml-3 tracking-widest uppercase">
            Renaissance Edition
          </span>
        </div>
      </div>

      {/* Right cluster */}
      <div className="flex items-center gap-4">
        {/* Live indicator */}
        <div className="hidden md:flex items-center gap-2 text-xs text-zinc-500">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          LIVE
        </div>

        {/* Clock */}
        <span className="hidden sm:block font-mono text-xs text-zinc-500 tabular-nums w-20 text-right">
          {clock}
        </span>

        <button
          onClick={handleLogout}
          className="flex items-center gap-1.5 text-xs text-zinc-500 hover:text-red-400 transition-colors px-2 py-1 rounded hover:bg-red-500/10"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">Logout</span>
        </button>
      </div>
    </header>
  );
}
