"use client";

import { useEffect, useRef } from "react";

const CURRENT_BUILD = process.env.NEXT_PUBLIC_BUILD_ID ?? "";
const VERSION_URL = `${process.env.NEXT_PUBLIC_BASE_PATH ?? ""}/version.json`;
const CHECK_EVERY_MS = 60_000;
const ATTEMPTS_KEY = "planer:update-attempts";

/**
 * Reload towards `build`, at most twice per build: a plain reload, then a cache-busting URL.
 * If the webview still serves the old page after that, give up instead of looping.
 */
function reloadTo(build: string) {
  let attempts: Record<string, number> = {};
  try {
    attempts = JSON.parse(sessionStorage.getItem(ATTEMPTS_KEY) ?? "{}");
  } catch {
    // Storage blocked: fall through with no history, still capped by the URL check below.
  }
  const tried = attempts[build] ?? 0;
  const url = new URL(window.location.href);
  if (tried >= 2 || url.searchParams.get("v") === build) return;
  attempts[build] = tried + 1;
  try {
    sessionStorage.setItem(ATTEMPTS_KEY, JSON.stringify(attempts));
  } catch {
    // Without storage the ?v= marker alone stops a second round.
  }
  if (tried === 0) {
    window.location.reload();
  } else {
    url.searchParams.set("v", build);
    window.location.replace(url.toString());
  }
}

/**
 * Reloads the Mini App when a newer build is deployed, so nobody has to restart Telegram.
 * Checks on open/focus and every minute; while `busy` (a sheet is open) it waits, then reloads.
 */
export function useAppUpdates(busy: boolean) {
  const pending = useRef<string | null>(null);
  const busyRef = useRef(busy);
  busyRef.current = busy;

  useEffect(() => {
    if (!CURRENT_BUILD || process.env.NODE_ENV !== "production") return;
    let stopped = false;

    const check = async () => {
      if (pending.current) return;
      try {
        const response = await fetch(`${VERSION_URL}?t=${Date.now()}`, { cache: "no-store" });
        if (!response.ok) return;
        const { build } = (await response.json()) as { build?: string };
        if (stopped || !build || build === CURRENT_BUILD) return;
        pending.current = build;
        if (!busyRef.current) reloadTo(build);
      } catch {
        // Offline or mid-deploy: try again on the next tick.
      }
    };

    const onVisible = () => {
      if (document.visibilityState === "visible") void check();
    };
    void check();
    const timer = setInterval(() => void check(), CHECK_EVERY_MS);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("focus", onVisible);
    return () => {
      stopped = true;
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("focus", onVisible);
    };
  }, []);

  // A newer build was found while editing: reload as soon as the sheet closes.
  useEffect(() => {
    if (!busy && pending.current) reloadTo(pending.current);
  }, [busy]);
}
