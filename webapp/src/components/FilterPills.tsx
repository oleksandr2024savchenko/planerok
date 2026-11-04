"use client";

import { motion } from "framer-motion";

import { cn } from "@/lib/cn";
import { FILTERS, type FilterId } from "@/lib/filters";
import { haptic } from "@/lib/telegram";

interface FilterPillsProps {
  value: FilterId;
  counts: Record<FilterId, number>;
  onChange: (value: FilterId) => void;
}

export function FilterPills({ value, counts, onChange }: FilterPillsProps) {
  return (
    <nav className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 py-1">
      {FILTERS.map((filter) => {
        const active = filter.id === value;
        return (
          <button
            key={filter.id}
            type="button"
            onClick={() => {
              if (active) return;
              haptic.selection();
              onChange(filter.id);
            }}
            className={cn(
              "relative flex shrink-0 items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-medium transition-colors",
              active
                ? "border-purple-500/50 text-purple-100"
                : "border-white/5 bg-zinc-900/60 text-zinc-400 hover:border-purple-500/30 hover:text-zinc-200",
            )}
          >
            {active && (
              <motion.span
                layoutId="active-filter"
                className="absolute inset-0 rounded-full bg-purple-500/15 shadow-[0_0_20px_rgba(168,85,247,0.25)]"
                transition={{ type: "spring", stiffness: 400, damping: 32 }}
              />
            )}
            <span className="relative">{filter.label}</span>
            <span
              className={cn(
                "relative min-w-5 rounded-full px-1.5 text-center font-mono text-[11px] tabular-nums",
                active ? "bg-purple-500/25 text-purple-100" : "bg-white/5 text-zinc-500",
              )}
            >
              {counts[filter.id] ?? 0}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
