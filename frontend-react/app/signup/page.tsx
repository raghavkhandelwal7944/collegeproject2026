"use client";

import { signup } from "@/lib/api";
import { motion } from "framer-motion";
import { Shield, UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

function Field({
  label,
  type = "text",
  value,
  onChange,
  autoComplete,
  required = true,
  placeholder,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  autoComplete?: string;
  required?: boolean;
  placeholder?: string;
}) {
  return (
    <div>
      <label className="block text-xs text-zinc-400 mb-1.5 tracking-wide">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        required={required}
        autoComplete={autoComplete}
        placeholder={placeholder}
        className="w-full bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-emerald-600/60 transition-colors"
      />
    </div>
  );
}

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    username: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const set = (field: keyof typeof form) => (value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (form.password !== form.confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    if (form.password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }

    setLoading(true);
    try {
      await signup(
        form.username.trim(),
        form.password,
        form.firstName.trim(),
        form.lastName.trim(),
        form.email.trim()
      );
      router.push("/login?registered=1");
    } catch (err: unknown) {
      setError((err as Error)?.message ?? "Signup failed. Try a different username.");
    } finally {
      setLoading(false);
    }
  };

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
        className="relative w-full max-w-md"
      >
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-8 shadow-2xl">
          {/* Icon */}
          <div className="flex justify-center mb-6">
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20">
              <Shield className="w-8 h-8 text-emerald-400" />
            </div>
          </div>

          <h1
            className="text-3xl font-bold text-center text-zinc-100 mb-1"
            style={{ fontFamily: "var(--font-serif)" }}
          >
            Create Account
          </h1>
          <p className="text-center text-xs text-zinc-500 tracking-widest uppercase mb-8">
            Firewall LLM
          </p>

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
            {/* Name row */}
            <div className="grid grid-cols-2 gap-3">
              <Field
                label="First Name"
                value={form.firstName}
                onChange={set("firstName")}
                autoComplete="given-name"
                placeholder="John"
              />
              <Field
                label="Last Name"
                value={form.lastName}
                onChange={set("lastName")}
                autoComplete="family-name"
                placeholder="Doe"
              />
            </div>

            <Field
              label="Email Address"
              type="email"
              value={form.email}
              onChange={set("email")}
              autoComplete="email"
              placeholder="john@example.com"
            />

            <Field
              label="Username"
              value={form.username}
              onChange={set("username")}
              autoComplete="username"
              placeholder="johndoe"
            />

            <div className="grid grid-cols-2 gap-3">
              <Field
                label="Password"
                type="password"
                value={form.password}
                onChange={set("password")}
                autoComplete="new-password"
              />
              <Field
                label="Confirm Password"
                type="password"
                value={form.confirmPassword}
                onChange={set("confirmPassword")}
                autoComplete="new-password"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-emerald-600/20 hover:bg-emerald-600/30 border border-emerald-700/50 text-emerald-400 text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              <UserPlus className="w-4 h-4" />
              {loading ? "Creating account…" : "Create Account"}
            </button>
          </form>

          <p className="text-center text-xs text-zinc-600 mt-6">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-zinc-400 hover:text-emerald-400 transition-colors"
            >
              Sign in
            </Link>
          </p>
        </div>
      </motion.div>
    </div>
  );
}
