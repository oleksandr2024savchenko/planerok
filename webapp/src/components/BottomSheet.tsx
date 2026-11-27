"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useId, type ReactNode } from "react";

interface BottomSheetProps {
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  children: ReactNode;
}

/** Shared modal sheet: backdrop, spring slide-up, Escape to close, body scroll lock. */
export function BottomSheet({ open, title, subtitle, onClose, children }: BottomSheetProps) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-labelledby={titleId}>
          <motion.button
            type="button"
            aria-label="Закрити"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
          />

          <motion.div
            className="absolute inset-x-0 bottom-0 max-h-[92dvh] overflow-y-auto rounded-t-3xl border border-white/10 border-b-0 bg-zinc-950/95 pb-safe shadow-[0_-20px_80px_rgba(0,0,0,0.55)] backdrop-blur-xl"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 32 }}
          >
            <div className="mx-auto mb-3 mt-3 h-1 w-10 rounded-full bg-white/15" />

            <div className="space-y-5 px-5 pb-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 id={titleId} className="text-lg font-semibold tracking-tight text-zinc-100">
                    {title}
                  </h2>
                  {subtitle && <p className="mt-0.5 text-sm text-zinc-500">{subtitle}</p>}
                </div>
                <button
                  type="button"
                  aria-label="Закрити"
                  onClick={onClose}
                  className="flex size-9 items-center justify-center rounded-full border border-white/5 bg-zinc-900 text-zinc-400 transition hover:border-purple-500/30 hover:text-zinc-100"
                >
                  <X className="size-4" />
                </button>
              </div>
              {children}
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

export const fieldClass =
  "w-full rounded-xl border border-white/5 bg-zinc-900/80 px-3 py-2.5 text-sm text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-purple-500/50 focus:shadow-[0_0_20px_rgba(168,85,247,0.15)] disabled:opacity-40";

export const chipClass = (active: boolean) =>
  active
    ? "border-purple-500/50 bg-purple-500/15 text-purple-100 shadow-[0_0_16px_rgba(168,85,247,0.2)]"
    : "border-white/5 bg-zinc-900/70 text-zinc-400 hover:border-purple-500/30 hover:text-zinc-200";

export const SPACE_COLORS = ["#a855f7", "#e879f9", "#38bdf8", "#34d399", "#fbbf24", "#fb7185"] as const;
export const DEFAULT_SPACE_COLOR = SPACE_COLORS[0];
