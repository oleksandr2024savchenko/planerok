export type Theme = "purple" | "pink";

/**
 * Telegram user ids that get the pink theme. Everyone else (including 969740172) sees purple.
 * NEXT_PUBLIC_PINK_USER_IDS="123,456" replaces the default list at build time.
 */
const DEFAULT_PINK_USER_IDS = "729424163";

const PINK_USER_IDS = new Set(
  (process.env.NEXT_PUBLIC_PINK_USER_IDS || DEFAULT_PINK_USER_IDS)
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean),
);

/** Kept purple explicitly, even if it ever lands in the pink list by mistake. */
const PURPLE_USER_IDS = new Set(["969740172"]);

export function themeForUser(userId: number | null | undefined): Theme {
  if (userId == null || PURPLE_USER_IDS.has(String(userId))) return "purple";
  return PINK_USER_IDS.has(String(userId)) ? "pink" : "purple";
}

/** `?theme=pink` / `?theme=purple` previews a theme without a Telegram account (demo, GitHub Pages). */
function themeFromUrl(): Theme | null {
  if (typeof window === "undefined") return null;
  const value = new URLSearchParams(window.location.search).get("theme");
  return value === "pink" || value === "purple" ? value : null;
}

export function applyTheme(userId: number | null | undefined): Theme {
  const theme = themeFromUrl() ?? themeForUser(userId);
  if (typeof document !== "undefined") {
    if (theme === "pink") document.documentElement.dataset.theme = "pink";
    else delete document.documentElement.dataset.theme;
  }
  return theme;
}
