"use client";

import { themeStore } from "@/lib/themeStore";
import { useSyncExternalStore } from "react";

export function ThemeToggle() {
  const theme = useSyncExternalStore(
    themeStore.subscribe.bind(themeStore),
    themeStore.getTheme.bind(themeStore),
    () => "dark" as const
  );

  const isDark = theme === "dark";

  return (
    <button
      onClick={() => themeStore.toggle()}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={isDark ? "Switch to light mode" : "Switch to dark mode"}
      className="theme-toggle-btn"
      style={{
        position: "relative",
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        width: "32px",
        height: "32px",
        borderRadius: "50%",
        border: "1px solid",
        borderColor: isDark ? "#3f3f46" : "#d4d4d8",
        background: isDark ? "#27272a" : "#f4f4f5",
        cursor: "pointer",
        transition: "background 200ms ease-in-out, border-color 200ms ease-in-out",
        flexShrink: 0,
      }}
    >
      {/* Sun */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill={isDark ? "#71717a" : "#d97706"}
        style={{
          position: "absolute",
          transition: "transform 200ms ease-in-out, opacity 200ms ease-in-out",
          transform: isDark ? "scale(0.1)" : "scale(1)",
          opacity: isDark ? 0 : 1,
        }}
      >
        <path d="M12,7a5,5,0,1,0,5,5,5,5,0,0,0-5-5Z" />
        <path d="M2,13H4a1,1,0,0,0,0-2H2a1,1,0,0,0,0,2Z" />
        <path d="M20,13h2a1,1,0,0,0,0-2H20a1,1,0,0,0,0,2Z" />
        <path d="M11,2V4a1,1,0,0,0,2,0V2a1,1,0,0,0-2,0Z" />
        <path d="M11,20v2a1,1,0,0,0,2,0V20a1,1,0,0,0-2,0Z" />
        <path d="M6,4.58A1,1,0,0,0,4.58,6L5.64,7.05A1,1,0,0,0,7.05,5.64Z" />
        <path d="M18.36,17A1,1,0,0,0,17,18.36L18,19.42A1,1,0,1,0,19.42,18Z" />
        <path d="M19.42,6A1,1,0,1,0,18,4.58L17,5.64a1,1,0,0,0,1.41,1.41Z" />
        <path d="M7.05,18.36A1,1,0,0,0,5.64,17L4.58,18A1,1,0,1,0,6,19.42Z" />
      </svg>

      {/* Moon */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill={isDark ? "#a1a1aa" : "#27272a"}
        style={{
          position: "absolute",
          transition: "transform 200ms ease-in-out, opacity 200ms ease-in-out",
          transform: isDark ? "scale(1)" : "scale(0.1)",
          opacity: isDark ? 1 : 0,
        }}
      >
        <path d="M11,3.05A9,9,0,1,0,21,13a1,1,0,0,0-1.54-.95,5.4,5.4,0,0,1-7.47-7.44A1,1,0,0,0,11,3.05Z" />
      </svg>
    </button>
  );
}
