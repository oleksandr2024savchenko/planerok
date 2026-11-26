"use client";

import { AnimatePresence, motion } from "framer-motion";
import { FileText, Link2, Menu, X } from "lucide-react";
import { useEffect, useId, useState } from "react";

import { cn } from "@/lib/cn";
import { SOFT_MOVE } from "@/lib/motion";
import { haptic } from "@/lib/telegram";
import type { CalendarStatus } from "@/lib/types";

interface SettingsBlockProps {
  status: CalendarStatus;
  onConnect: () => void;
  onImport?: () => void;
}

export function SettingsBlock({ status, onConnect, onImport }: SettingsBlockProps) {
  const menuId = useId();
  const [open, setOpen] = useState(false);
  const detail = status.live ? "Наживо" : status.connected ? "Підключено" : "Немає зв’язку";

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  function toggle() {
    haptic.selection();
    setOpen((current) => !current);
  }

  return (
    <div className={cn("relative shrink-0", open && "z-40")}>
      <button
        type="button"
        aria-label="Налаштування"
        aria-expanded={open}
        aria-controls={menuId}
        onClick={toggle}
        className={cn(
          "relative z-30 flex size-9 items-center justify-center rounded-full border bg-zinc-900 text-zinc-300",
          open ? "border-purple-500/40 text-zinc-100" : "border-white/10 hover:border-purple-500/30 hover:text-zinc-100",
        )}
      >
        {open ? <X className="size-4" /> : <Menu className="size-4" />}
      </button>

      <AnimatePresence>
        {open && (
          <>
            <button
              type="button"
              aria-label="Закрити налаштування"
              className="fixed inset-0 z-20 cursor-default"
              onClick={() => setOpen(false)}
            />
            <motion.div
              id={menuId}
              role="menu"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={SOFT_MOVE}
              className="absolute right-0 top-11 z-40 w-64 rounded-2xl border border-white/10 bg-[var(--void)] p-3 shadow-[0_20px_60px_rgba(0,0,0,0.55)]"
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-500">Налаштування</p>
              <div className="mt-3 flex items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5">
                <span className="relative flex size-2 shrink-0">
                  {status.live && (
                    <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-70" />
                  )}
                  <span
                    className={cn(
                      "relative size-2 rounded-full",
                      status.live ? "bg-emerald-400" : status.connected ? "bg-purple-400" : "bg-zinc-500",
                    )}
                  />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-medium leading-5 text-zinc-100">Google Sync</span>
                  <span className="block text-xs leading-4 text-zinc-500">{detail}</span>
                </span>
              </div>
              <button
                type="button"
                role="menuitem"
                onClick={() => {
                  haptic.selection();
                  setOpen(false);
                  onConnect();
                }}
                className="mt-2 flex w-full items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-left text-sm font-medium text-zinc-100 hover:border-white/20"
              >
                <Link2 className="size-4 shrink-0 text-zinc-400" aria-hidden />
                Календар за посиланням
              </button>
              {onImport && (
                <button
                  type="button"
                  role="menuitem"
                  onClick={() => {
                    haptic.selection();
                    setOpen(false);
                    onImport();
                  }}
                  className="mt-2 flex w-full items-center gap-2.5 rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2.5 text-left text-sm font-medium text-zinc-100 hover:border-white/20"
                >
                  <FileText className="size-4 shrink-0 text-zinc-400" aria-hidden />
                  Розклад з PDF
                </button>
              )}
              <p className="mt-3 text-center text-[10px] tracking-wide text-zinc-600">
                Версія {process.env.NEXT_PUBLIC_BUILD_ID || "dev"}
              </p>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
