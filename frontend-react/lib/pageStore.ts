/**
 * Module-level page cache — survives React component unmounts.
 *
 * Each page can store its fetched data here so that when the user
 * navigates back, data renders instantly instead of refetching.
 * Entries expire after maxAgeMs (default 30 s).
 */

interface CacheEntry<T = unknown> {
  data: T;
  fetchedAt: number;
}

const _cache = new Map<string, CacheEntry>();

export const pageStore = {
  /** Store data for a key. */
  set<T>(key: string, data: T): void {
    _cache.set(key, { data, fetchedAt: Date.now() });
  },

  /** Retrieve cached data (or undefined if not set). */
  get<T>(key: string): T | undefined {
    return _cache.get(key)?.data as T | undefined;
  },

  /** Returns true if data exists and was fetched within maxAgeMs. */
  isFresh(key: string, maxAgeMs = 30_000): boolean {
    const entry = _cache.get(key);
    if (!entry) return false;
    return Date.now() - entry.fetchedAt < maxAgeMs;
  },

  /** Evict a key. */
  clear(key: string): void {
    _cache.delete(key);
  },
};
