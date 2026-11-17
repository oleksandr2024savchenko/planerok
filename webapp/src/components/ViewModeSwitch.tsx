"use client";

import { CalendarDays, List } from "lucide-react";

import { SegmentedControl } from "@/components/SegmentedControl";
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
    <SegmentedControl
      layoutId="view-mode"
      value={value}
      options={MODES.map(({ id, label, icon: Icon }) => ({
        id,
        label: (
          <>
            <Icon className="size-3.5 shrink-0" aria-hidden />
            <span className="shrink-0">{label}</span>
          </>
        ),
      }))}
      onChange={(next) => {
        haptic.selection();
        onChange(next);
      }}
    />
  );
}
