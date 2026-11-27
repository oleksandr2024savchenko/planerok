"use client";

import { Sun } from "lucide-react";
import { useEffect, useState } from "react";

import { notificationsApi, USE_MOCKS } from "@/lib/api";
import { cn } from "@/lib/cn";
import { haptic } from "@/lib/telegram";
import type { NotificationPrefs } from "@/lib/types";

import { BottomSheet, fieldClass } from "./BottomSheet";

const DEFAULT_PREFS: NotificationPrefs = { digest_enabled: true, digest_time: "08:00" };

interface DigestSheetProps {
  open: boolean;
  onClose: () => void;
}

export function DigestSheet({ open, onClose }: DigestSheetProps) {
  const [prefs, setPrefs] = useState<NotificationPrefs | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setSaved(false);
    if (USE_MOCKS) {
      setPrefs((current) => current ?? DEFAULT_PREFS);
      return;
    }
    notificationsApi
      .get()
      .then(setPrefs)
      .catch(() => setError("Не вдалося завантажити налаштування"));
  }, [open]);

  async function save(patch: Partial<NotificationPrefs>) {
    if (!prefs) return;
    const previous = prefs;
    setPrefs({ ...prefs, ...patch });
    setError(null);
    try {
      if (!USE_MOCKS) setPrefs(await notificationsApi.update(patch));
      haptic.notify("success");
      setSaved(true);
    } catch {
      setPrefs(previous);
      haptic.notify("error");
      setError("Не вдалося зберегти");
    }
  }

  return (
    <BottomSheet
      open={open}
      title="Ранковий дайджест"
      subtitle="Бот щоранку надсилає задачі на сьогодні, прострочені й серії звичок."
      onClose={onClose}
    >
      {prefs && (
        <div className="space-y-4">
          <button
            type="button"
            role="switch"
            aria-checked={prefs.digest_enabled}
            onClick={() => {
              haptic.selection();
              void save({ digest_enabled: !prefs.digest_enabled });
            }}
            className="flex w-full items-center gap-3 rounded-2xl border border-white/5 bg-zinc-900/60 px-3.5 py-3 text-left transition hover:border-purple-500/30"
          >
            <span className="flex size-9 items-center justify-center rounded-xl border border-purple-500/20 bg-purple-500/10">
              <Sun className="size-4 text-purple-300" />
            </span>
            <span className="flex-1">
              <span className="block text-[15px] font-medium text-zinc-100">Надсилати дайджест</span>
              <span className="block text-[11px] text-zinc-500">
                {prefs.digest_enabled ? `Щодня о ${prefs.digest_time}` : "Вимкнено"}
              </span>
            </span>
            <span
              aria-hidden
              className={cn(
                "relative h-6 w-11 rounded-full border transition",
                prefs.digest_enabled
                  ? "border-purple-500/50 bg-purple-500/40 shadow-[0_0_12px_rgba(168,85,247,0.35)]"
                  : "border-white/10 bg-zinc-800",
              )}
            >
              <span
                className={cn(
                  "absolute top-0.5 size-[18px] rounded-full bg-white transition-all",
                  prefs.digest_enabled ? "left-[22px]" : "left-0.5",
                )}
              />
            </span>
          </button>

          <label className="block space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">Час</span>
            <input
              type="time"
              value={prefs.digest_time}
              disabled={!prefs.digest_enabled}
              onChange={(event) => {
                if (event.target.value) void save({ digest_time: event.target.value });
              }}
              className={fieldClass}
            />
          </label>

          <p className="text-xs leading-relaxed text-zinc-500">
            У боті: <code className="text-zinc-400">/digest 07:30</code>, <code className="text-zinc-400">/digest off</code>
            {" "}або <code className="text-zinc-400">/digest now</code>, щоб отримати його одразу.
          </p>
        </div>
      )}
      {saved && !error && <p className="text-sm text-emerald-400/90">Збережено</p>}
      {error && <p className="text-sm text-rose-400">{error}</p>}
    </BottomSheet>
  );
}
