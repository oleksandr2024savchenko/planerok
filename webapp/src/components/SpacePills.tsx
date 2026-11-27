"use client";

import { FolderPlus, Settings2 } from "lucide-react";

import { cn } from "@/lib/cn";
import { haptic } from "@/lib/telegram";
import type { Space } from "@/lib/types";

import { DEFAULT_SPACE_COLOR } from "./BottomSheet";

export type SpaceFilter = number | "all";

interface SpacePillsProps {
  spaces: Space[];
  value: SpaceFilter;
  onChange: (value: SpaceFilter) => void;
  onManage: () => void;
}

export function SpaceDot({ color }: { color: string | null }) {
  const tone = color ?? DEFAULT_SPACE_COLOR;
  return (
    <span
      aria-hidden
      className="size-2 shrink-0 rounded-full"
      style={{ backgroundColor: tone, boxShadow: `0 0 8px ${tone}99` }}
    />
  );
}

const pill = "flex shrink-0 items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium transition-colors";
const idle = "border-white/5 bg-zinc-900/60 text-zinc-400 hover:border-purple-500/30 hover:text-zinc-200";
const active = "border-purple-500/50 bg-purple-500/15 text-purple-100 shadow-[0_0_16px_rgba(168,85,247,0.2)]";

/** Space switcher above the task filters. With a single space it only offers to create one. */
export function SpacePills({ spaces, value, onChange, onManage }: SpacePillsProps) {
  if (spaces.length <= 1) {
    return (
      <button type="button" onClick={onManage} className={cn(pill, idle)}>
        <FolderPlus className="size-3.5" />
        Простори
      </button>
    );
  }

  const select = (next: SpaceFilter) => {
    if (next === value) return;
    haptic.selection();
    onChange(next);
  };

  return (
    <nav className="no-scrollbar -mx-5 flex gap-2 overflow-x-auto px-5 py-1" aria-label="Простори">
      <button type="button" onClick={() => select("all")} className={cn(pill, value === "all" ? active : idle)}>
        Усі простори
      </button>
      {spaces.map((space) => (
        <button
          key={space.id}
          type="button"
          onClick={() => select(space.id)}
          className={cn(pill, value === space.id ? active : idle)}
        >
          <SpaceDot color={space.color} />
          {space.name}
        </button>
      ))}
      <button type="button" aria-label="Керувати просторами" onClick={onManage} className={cn(pill, idle, "px-2")}>
        <Settings2 className="size-3.5" />
      </button>
    </nav>
  );
}
