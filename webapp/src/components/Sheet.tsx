"use client";

import { motion, useReducedMotion } from "framer-motion";
import { useEffect, type ReactNode } from "react";

import { useMotionProfile } from "@/hooks/useMotionProfile";
import { cn } from "@/lib/cn";
import { SHEET_MOTION } from "@/lib/motion";

/**
 * Backdrop + bottom panel shared by the task and calendar sheets.
 *
 * The panel moves with a `transform` string, which framer-motion hands to the browser's
 * compositor (Web Animations API). The slide keeps its frame rate even while React is still
 * building the form inside it, which is what made the sheet stutter before.
 */
export function SheetBackdrop({ onClose }: { onClose: () => void }) {
  const profile = useMotionProfile();
  const reduce = useReducedMotion();
  return (
    <motion.button
      type="button"
      aria-label="Закрити"
      className="sheet-backdrop absolute inset-0 bg-black/60"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: reduce ? 0 : SHEET_MOTION[profile].backdrop, ease: "easeOut" }}
      onClick={onClose}
    />
  );
}

export function SheetPanel({ className, children }: { className?: string; children: ReactNode }) {
  const profile = useMotionProfile();
  const reduce = useReducedMotion();
  const timing = SHEET_MOTION[profile];

  // Background flowers pause while a sheet is open, so their repaints don't steal frames.
  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("sheet-open");
    return () => root.classList.remove("sheet-open");
  }, []);

  return (
    <motion.div
      className={cn(
        "sheet-surface absolute inset-x-0 bottom-0 mx-auto max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-3xl border border-b-0 border-white/10 bg-zinc-950/95 pb-safe shadow-[0_-20px_80px_rgba(0,0,0,0.55)]",
        className,
      )}
      style={{ willChange: "transform" }}
      initial={{ transform: "translateY(100%)" }}
      animate={{ transform: "translateY(0%)", transition: reduce ? { duration: 0 } : timing.open }}
      exit={{ transform: "translateY(100%)", transition: reduce ? { duration: 0 } : timing.close }}
    >
      {children}
    </motion.div>
  );
}
