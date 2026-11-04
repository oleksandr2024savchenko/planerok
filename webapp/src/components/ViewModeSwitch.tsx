"use client";

import { CalendarDays, List } from "lucide-react";

import { cn } from "@/lib/cn";
import { haptic } from "@/lib/telegram";

export type ViewMode = "list" | "calendar";

const MODES: { id: ViewMode; label: string; icon: typeof List }[] = [
  { id: "list", label: "Список", icon: List },
  { id: "calendar", label: "Календар", icon: CalendarDays },
];

interface ViewModeSwitchProps {
  value: ViewMode;
  onChange: (value: ViewMode) => void;
}

export function ViewModeSwitch({ value, onChange }: ViewModeSwitchProps) {
  return (
    <div className="flex rounded-full border border-white/5 bg-zinc-900/60 p-1 backdrop-blur-md">
      {MODES.map((mode) => {
        const active = mode.id === value;
        const Icon = mode.icon;
        return (
          <button
            key={mode.id}
            type="button"
            onClick={() => {
              if (active) return;
              haptic.selection();
              onChange(mode.id);
            }}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium transition",
              active
                ? "bg-purple-500/20 text-purple-100 shadow-[0_0_16px_rgba(168,85,247,0.25)]"
                : "text-zinc-400 hover:text-zinc-200",
            )}
          >
            <Icon className="size-3.5" />
            {mode.label}
          </button>
        );
      })}
    </div>
  );
}
