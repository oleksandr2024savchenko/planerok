"use client";

import { cn } from "@/lib/cn";
import type { CalendarStatus } from "@/lib/types";

export function SyncBadge({ status }: { status: CalendarStatus }) {
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-white/5 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-200 backdrop-blur-md">
      <span className="relative flex size-2">
        {status.live && (
          <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-70" />
        )}
        <span
          className={cn(
            "relative size-2 rounded-full",
            status.live
              ? "bg-emerald-400 shadow-[0_0_10px_#34d399]"
              : "bg-purple-500 shadow-[0_0_10px_#A855F7]",
          )}
        />
      </span>
      {status.live ? "🔄 Google Sync Live" : status.connected ? "🔄 Google Sync" : "Google Sync offline"}
    </div>
  );
}
