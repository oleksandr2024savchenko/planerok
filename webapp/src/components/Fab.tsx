"use client";

import { Plus } from "lucide-react";

import { haptic } from "@/lib/telegram";

interface FabProps {
  onClick: () => void;
  hidden?: boolean;
}

export function Fab({ onClick, hidden }: FabProps) {
  return (
    <button
      type="button"
      aria-label="Додати задачу"
      aria-hidden={hidden}
      tabIndex={hidden ? -1 : 0}
      onClick={() => {
        haptic.impact("medium");
        onClick();
      }}
      className="fixed z-30 flex size-14 items-center justify-center rounded-full bg-purple-600 text-white shadow-[0_0_25px_rgba(168,85,247,0.6)] transition duration-200 hover:bg-purple-500 hover:shadow-[0_0_32px_rgba(168,85,247,0.8)] active:scale-95 disabled:pointer-events-none disabled:opacity-0"
      style={{
        bottom: "max(1.25rem, calc(env(safe-area-inset-bottom) + 0.75rem))",
        right: "max(1.25rem, calc(50% - 16rem + 1.25rem))",
      }}
      disabled={hidden}
    >
      <Plus className="size-7" strokeWidth={2.25} />
    </button>
  );
}
