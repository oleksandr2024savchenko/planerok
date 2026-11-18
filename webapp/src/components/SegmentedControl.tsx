"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/cn";
import { FADE, GLIDE } from "@/lib/motion";

function ActiveFill({ layoutId }: { layoutId: string }) {
  const reduce = useReducedMotion();
  return (
    <motion.span
      layoutId={layoutId}
      aria-hidden
      className="choice-fill pointer-events-none absolute inset-0 rounded-[inherit]"
      transition={reduce ? { duration: 0 } : GLIDE}
    />
  );
}

/**
 * Inside a sheet that is itself sliding, a travelling pill would drift with it, so the fill
 * cross-fades in place instead: the old one dissolves while the new one grows in.
 */
function InPlaceFill({ active }: { active: boolean }) {
  const reduce = useReducedMotion();
  return (
    <AnimatePresence initial={false}>
      {active && (
        <motion.span
          aria-hidden
          className="choice-fill pointer-events-none absolute inset-0 rounded-[inherit]"
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.96 }}
          transition={reduce ? { duration: 0 } : FADE}
        />
      )}
    </AnimatePresence>
  );
}

interface SegmentedOption<T extends string> {
  id: T;
  label: ReactNode;
}

interface SegmentedControlProps<T extends string> {
  value: T;
  options: readonly SegmentedOption<T>[];
  onChange: (value: T) => void;
  layoutId: string;
  className?: string;
  fullWidth?: boolean;
  size?: "sm" | "md";
  /** Paint the selection in place. Use inside animated sheets, where a sliding pill drifts. */
  anchored?: boolean;
}

export function SegmentedControl<T extends string>({
  value,
  options,
  onChange,
  layoutId,
  className,
  fullWidth = false,
  size = "md",
  anchored = false,
}: SegmentedControlProps<T>) {
  return (
    <div
      className={cn(
        "grid gap-1 rounded-full border border-white/10 bg-zinc-950/40 p-1",
        fullWidth ? "w-full" : "w-max max-w-full",
        className,
      )}
      style={{ gridTemplateColumns: `repeat(${options.length}, minmax(0, 1fr))` }}
    >
      {options.map((option) => {
        const active = option.id === value;
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={active}
            onClick={() => {
              if (active) return;
              onChange(option.id);
            }}
            className={cn(
              "press relative min-w-0 rounded-full font-medium transition-[color,background-color,scale] duration-300",
              size === "sm" ? "px-2 py-1 text-xs" : "px-2 py-1.5 text-[13px] min-[380px]:text-sm",
              active ? "text-white" : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100",
            )}
          >
            {anchored ? <InPlaceFill active={active} /> : active && <ActiveFill layoutId={layoutId} />}
            <span className="relative z-10 flex w-full min-w-0 items-center justify-center gap-1.5">
              {typeof option.label === "string" ? (
                <span className="min-w-0 truncate">{option.label}</span>
              ) : (
                option.label
              )}
            </span>
          </button>
        );
      })}
    </div>
  );
}

interface ChoiceChipProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active: boolean;
  layoutId: string;
  anchored?: boolean;
}

export function ChoiceChip({ active, layoutId, anchored = false, className, children, ...props }: ChoiceChipProps) {
  return (
    <button
      type="button"
      aria-pressed={active}
      className={cn(
        "press relative max-w-full shrink-0 rounded-full border px-3 py-1.5 text-sm font-medium transition-[color,background-color,border-color,scale] duration-300",
        active
          ? "border-transparent text-white"
          : "border-white/10 bg-white/[0.04] text-zinc-400 hover:border-white/20 hover:text-zinc-100",
        className,
      )}
      {...props}
    >
      {anchored ? <InPlaceFill active={active} /> : active && <ActiveFill layoutId={layoutId} />}
      <span className="relative z-10 inline-flex w-full min-w-0 items-center justify-center gap-1.5">{children}</span>
    </button>
  );
}
