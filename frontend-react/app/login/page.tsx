"use client";

import { login } from "@/lib/api";
import { motion } from "framer-motion";
import { LogIn, Shield } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

// ── Inner form — isolated here so useSearchParams is inside Suspense ──
function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const justRegistered = searchParams.get("registered") === "1";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(username, password);
      router.push("/dashboard");
    } catch (err: unknown) {
      setError((err as Error)?.message ?? "Invalid credentials");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-2xl">
      {/* Icon */}
      <div className="flex justify-center mb-6">
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
          <Shield className="w-8 h-8 text-emerald-400" />
        </div>
      </div>

      {/* Heading */}
      <h1
        className="text-3xl font-bold text-center text-zinc-100 mb-1"
        style={{ fontFamily: "var(--font-serif)" }}
      >
        Firewall LLM
      </h1>
      <p className="text-center text-xs text-zinc-500 tracking-widest uppercase mb-8">
        Renaissance Edition
      </p>

      {/* Success — redirected from signup */}
      {justRegistered && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 px-3 py-2 rounded-lg bg-emerald-950/60 border border-emerald-800/50 text-emerald-400 text-sm text-center"
        >
          Account created! Please sign in.
        </motion.div>
      )}

      {/* Error */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -4 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-4 px-3 py-2 rounded-lg bg-red-950/60 border border-red-800/50 text-red-400 text-sm text-center"
        >
          {error}
        </motion.div>
      )}

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-xs text-zinc-400 mb-1.5 tracking-wide">
            Username
          </label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="username"
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-600/60 transition-colors"
          />
        </div>

        <div>
          <label className="block text-xs text-zinc-400 mb-1.5 tracking-wide">
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoComplete="current-password"
            className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-600/60 transition-colors"
          />
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-700/50 text-emerald-400 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
        >
          <LogIn className="w-4 h-4" />
          {loading ? "Authenticating…" : "Enter Firewall"}
        </button>
      </form>

      <p className="text-center text-xs text-zinc-600 mt-6">
        No account?{" "}
        <Link
          href="/signup"
          className="text-zinc-400 hover:text-emerald-400 transition-colors"
        >
          Create one
        </Link>
      </p>
    </div>
  );
}

// ── Page shell ────────────────────────────────────────────────────────
export default function LoginPage() {
  return (
    <div className="min-h-screen bg-zinc-950 flex items-center justify-center p-4">
      {/* Subtle grid backdrop */}
      <div
        className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(#fafafa 1px, transparent 1px), linear-gradient(90deg, #fafafa 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative w-full max-w-sm"
      >
        {/* Suspense required by Next.js 15+ when useSearchParams is used */}
        <Suspense
          fallback={
            <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 flex items-center justify-center min-h-[400px]">
              <div className="w-5 h-5 border-2 border-emerald-500 border-t-transparent rounded-full animate-spin" />
            </div>
          }
        >
          <LoginForm />
        </Suspense>

        {/* Footer */}
        <p className="text-center text-[10px] text-zinc-700 mt-4 tracking-widest uppercase">
          All traffic is encrypted end-to-end
        </p>
      </motion.div>
    </div>
  );
}