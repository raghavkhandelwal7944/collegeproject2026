"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
    Activity,
    ChevronLeft,
    LayoutDashboard,
    Menu,
    MessageSquare,
    Settings2,
    Shield,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
}

const NAV_ITEMS = [
  {
    href: "/dashboard",
    label: "Overview",
    icon: LayoutDashboard,
    description: "Stats & telemetry",
  },
  {
    href: "/traffic",
    label: "Live Traffic",
    icon: Activity,
    description: "All request logs",
  },
  {
    href: "/playground",
    label: "Playground",
    icon: MessageSquare,
    description: "Test the firewall",
  },
  {
    href: "/policies",
    label: "Policies",
    icon: Settings2,
    description: "Engine settings",
  },
];

export function Sidebar({ open, onToggle }: SidebarProps) {
  const pathname = usePathname();

  return (
    <>
      {/* ── Backdrop for mobile ─────────────────── */}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-20 bg-black/60 lg:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onToggle}
          />
        )}
      </AnimatePresence>

      {/* ── Sidebar panel ───────────────────────── */}
      <motion.aside
        className="fixed top-0 left-0 z-30 h-full flex flex-col bg-zinc-950 border-r border-zinc-800 overflow-hidden"
        animate={{ width: open ? 220 : 56 }}
        transition={{ type: "spring", stiffness: 300, damping: 30 }}
      >
        {/* Header: logo + toggle */}
        <div className="flex items-center h-14 border-b border-zinc-800 shrink-0 px-3 gap-3">
          {/* Always-visible shield icon */}
          <div className="shrink-0 p-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20">
            <Shield className="w-4 h-4 text-emerald-400" />
          </div>

          {/* Brand text — visible only when open */}
          <AnimatePresence>
            {open && (
              <motion.span
                className="text-xs font-bold tracking-widest uppercase text-zinc-100 whitespace-nowrap overflow-hidden"
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: "auto" }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.18 }}
                style={{ fontFamily: "var(--font-serif)" }}
              >
                Firewall LLM
              </motion.span>
            )}
          </AnimatePresence>

          {/* Hamburger / chevron toggle — pushed to right when open */}
          <button
            onClick={onToggle}
            className="ml-auto shrink-0 p-1 rounded hover:bg-zinc-800 text-zinc-500 hover:text-zinc-200 transition-colors"
            aria-label={open ? "Collapse sidebar" : "Expand sidebar"}
          >
            {open ? (
              <ChevronLeft className="w-4 h-4" />
            ) : (
              <Menu className="w-4 h-4" />
            )}
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 flex flex-col gap-1 px-2 py-3 overflow-y-auto scrollbar-thin">
          {NAV_ITEMS.map(({ href, label, icon: Icon, description }) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                className={`
                  relative flex items-center gap-3 px-2 py-2.5 rounded-lg transition-colors group
                  ${
                    active
                      ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                      : "hover:bg-zinc-800/70 text-zinc-500 hover:text-zinc-200 border border-transparent"
                  }
                `}
              >
                <Icon className="w-4 h-4 shrink-0" />

                <AnimatePresence>
                  {open && (
                    <motion.div
                      className="overflow-hidden"
                      initial={{ opacity: 0, width: 0 }}
                      animate={{ opacity: 1, width: "auto" }}
                      exit={{ opacity: 0, width: 0 }}
                      transition={{ duration: 0.15 }}
                    >
                      <p className="text-xs font-medium whitespace-nowrap leading-none">
                        {label}
                      </p>
                      <p className="text-[10px] text-zinc-600 whitespace-nowrap mt-0.5 leading-none">
                        {description}
                      </p>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* Tooltip when collapsed */}
                {!open && (
                  <div className="absolute left-full ml-3 px-2 py-1 rounded bg-zinc-800 border border-zinc-700 text-xs text-zinc-200 whitespace-nowrap opacity-0 group-hover:opacity-100 pointer-events-none transition-opacity z-50">
                    {label}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom version */}
        <AnimatePresence>
          {open && (
            <motion.div
              className="px-4 py-3 border-t border-zinc-900"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <p className="text-[10px] text-zinc-700 font-mono">
                Phase 4 · Renaissance Edition
              </p>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.aside>
    </>
  );
}
