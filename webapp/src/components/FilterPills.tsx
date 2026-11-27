"use client";

import { ChoiceChip, SegmentedControl } from "@/components/SegmentedControl";
import { cn } from "@/lib/cn";
import { AUDIENCES, FILTERS, type AudienceId, type FilterId } from "@/lib/filters";
import { haptic } from "@/lib/telegram";

interface FilterPillsProps {
  value: FilterId;
  counts: Record<FilterId, number>;
  onChange: (value: FilterId) => void;
}

export function AudiencePills({
  value,
  onChange,
}: {
  value: AudienceId;
  onChange: (value: AudienceId) => void;
}) {
  return (
    <SegmentedControl
      fullWidth
      layoutId="audience"
      value={value}
      options={AUDIENCES}
      onChange={(next) => {
        haptic.selection();
        onChange(next);
      }}
      className="mb-3"
    />
  );
}

export function FilterPills({ value, counts, onChange }: FilterPillsProps) {
  return (
    <nav className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 py-1.5">
      {FILTERS.map((filter) => {
        const active = filter.id === value;
        return (
          <ChoiceChip
            key={filter.id}
            layoutId="active-filter"
            active={active}
            onClick={() => {
              if (active) return;
              haptic.selection();
              onChange(filter.id);
            }}
          >
            <span>{filter.label}</span>
            <span
              className={cn(
                "min-w-5 rounded-full px-1.5 text-center font-mono text-[11px] tabular-nums transition-colors duration-300",
                active ? "bg-white/25 text-white" : "bg-white/10 text-zinc-500",
              )}
            >
              {counts[filter.id] ?? 0}
            </span>
          </ChoiceChip>
        );
      })}
    </nav>
  );
}
