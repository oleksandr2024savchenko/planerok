"use client";

import { useEffect, useState } from "react";

import { calendarApi, USE_MOCKS } from "@/lib/api";
import type { CalendarStatus } from "@/lib/types";

/** Live Google connection. Mock mode has no calendar, so the hook stays idle. */
export function useCalendarStatus(enabled: boolean) {
  const [status, setStatus] = useState<CalendarStatus | null>(null);

  useEffect(() => {
    if (!enabled || USE_MOCKS) return;
    let cancelled = false;
    calendarApi
      .status()
      .then((value) => {
        if (!cancelled) setStatus(value);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, [enabled]);

  return status;
}
