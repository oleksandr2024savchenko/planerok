"use client";

import { useSyncExternalStore } from "react";

import type { MotionProfile } from "@/lib/motion";

function read(): MotionProfile {
  return document.documentElement.dataset.theme === "pink" ? "lite" : "fluid";
}

function subscribe(onChange: () => void) {
  const observer = new MutationObserver(onChange);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

/** "fluid" for the violet (120 Hz) account, "lite" for the pink (60 Hz) one. */
export function useMotionProfile(): MotionProfile {
  return useSyncExternalStore(subscribe, read, () => "fluid");
}
