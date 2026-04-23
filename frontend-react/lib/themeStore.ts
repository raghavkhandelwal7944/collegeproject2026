/**
 * Module-level theme store — survives React component unmounts.
 *
 * Persists the preferred theme in localStorage and applies the
 * "dark" / "light" class on <html> so Tailwind's darkMode:"class"
 * utilities work everywhere.
 */

type Theme = "dark" | "light";
type Listener = () => void;

// Read persisted preference; default to dark
let _theme: Theme =
  (typeof window !== "undefined" &&
    (localStorage.getItem("theme") as Theme | null)) ||
  "dark";

const _listeners = new Set<Listener>();

function notify() {
  _listeners.forEach((l) => l());
}

/** Apply the class to <html> and persist. */
function applyTheme(t: Theme) {
  if (typeof document === "undefined") return;
  const html = document.documentElement;
  html.classList.remove("dark", "light");
  html.classList.add(t);
  localStorage.setItem("theme", t);
}

// Apply on module load (runs once when imported)
applyTheme(_theme);

export const themeStore = {
  getTheme(): Theme {
    return _theme;
  },

  setTheme(t: Theme): void {
    _theme = t;
    applyTheme(t);
    notify();
  },

  toggle(): void {
    themeStore.setTheme(_theme === "dark" ? "light" : "dark");
  },

  subscribe(listener: Listener): () => void {
    _listeners.add(listener);
    return () => _listeners.delete(listener);
  },
};
