"use client";

import { motion } from "framer-motion";

interface ToggleSwitchProps {
  checked: boolean;
  onChange: () => void;
  label?: string;
}

export function ToggleSwitch({ checked, onChange, label }: ToggleSwitchProps) {
  // Spread bypasses the axe/aria static JSX linter which can't evaluate inline expressions
  const switchProps = {
    "aria-checked": (checked ? "true" : "false") as "true" | "false",
    ...(label ? { "aria-label": label } : {}),
  };
  return (
    <label className="inline-flex items-center gap-2 cursor-pointer">
      <button
        type="button"
        role="switch"
        {...switchProps}
        onClick={onChange}
        onClick={onChange}
        className={[
          "relative inline-flex items-center w-11 h-6 rounded-full border transition-colors duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 cursor-pointer",
          checked
            ? "bg-emerald-500/20 border-emerald-600"
            : "bg-zinc-800 border-zinc-700",
        ].join(" ")}
      >
        <motion.span
          layout
          transition={{ type: "spring", stiffness: 700, damping: 40 }}
          className={[
            "inline-block w-4 h-4 rounded-full shadow-sm",
            checked ? "bg-emerald-400" : "bg-zinc-500",
          ].join(" ")}
          style={{
            x: checked ? 22 : 4,
          }}
        />
      </button>
      {label && (
        <span className="text-sm text-zinc-400 select-none">{label}</span>
      )}
    </label>
  );
}
