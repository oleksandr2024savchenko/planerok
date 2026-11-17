"use client";

import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { useEffect, useId, useState, type FormEvent } from "react";

import { calendarApi, USE_MOCKS } from "@/lib/api";
import { SOFT_MOVE } from "@/lib/motion";
import { haptic } from "@/lib/telegram";
import type { CalendarFeed } from "@/lib/types";

interface ExternalCalendarSheetProps {
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}

export function ExternalCalendarSheet({ open, onClose, onChanged }: ExternalCalendarSheetProps) {
  const titleId = useId();
  const [feeds, setFeeds] = useState<CalendarFeed[]>([]);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setError(null);
    if (USE_MOCKS) return;
    let cancelled = false;
    calendarApi
      .feeds()
      .then((next) => {
        if (!cancelled) setFeeds(next);
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Не вдалося завантажити календарі");
      });
    return () => {
      cancelled = true;
    };
  }, [open]);

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

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      setError("Встав посилання на календар");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const saved = await calendarApi.connect(trimmed, name.trim() || undefined);
      setFeeds((current) => [saved, ...current.filter((feed) => feed.id !== saved.id)]);
      setUrl("");
      setName("");
      haptic.notify("success");
      onChanged();
    } catch (err) {
      haptic.notify("error");
      setError(err instanceof Error ? err.message : "Не вдалося підключити календар");
    } finally {
      setSubmitting(false);
    }
  }

  async function remove(id: number) {
    setError(null);
    try {
      await calendarApi.disconnect(id);
      setFeeds((current) => current.filter((feed) => feed.id !== id));
      haptic.impact("light");
      onChanged();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не вдалося відключити календар");
    }
  }

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
            className="absolute inset-x-0 bottom-0 mx-auto max-h-[92dvh] w-full max-w-lg overflow-y-auto rounded-t-3xl border border-white/10 border-b-0 bg-zinc-950/95 pb-safe shadow-[0_-20px_80px_rgba(0,0,0,0.55)] backdrop-blur-xl"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ duration: 0.42, ease: SOFT_MOVE.ease }}
          >
            <div className="mx-auto mb-2 mt-3 h-1 w-10 rounded-full bg-white/15" />
            <form onSubmit={(event) => void handleSubmit(event)} className="space-y-4 px-4 pb-5 sm:px-5">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 id={titleId} className="text-lg font-semibold tracking-tight text-zinc-100">
                    Календар за посиланням
                  </h2>
                  <p className="mt-0.5 text-sm leading-snug text-zinc-500">
                    Події зʼявляться в планерi. Їх не можна редагувати, і вони не потрапляють у твій Google Calendar.
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Закрити"
                  onClick={onClose}
                  className="flex size-9 shrink-0 items-center justify-center rounded-full border border-white/10 bg-zinc-900 text-zinc-400"
                >
                  <X className="size-4" />
                </button>
              </div>

              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">Посилання iCal</span>
                <input
                  value={url}
                  onChange={(event) => setUrl(event.target.value)}
                  placeholder="https://… або webcal://…"
                  inputMode="url"
                  autoCapitalize="none"
                  autoCorrect="off"
                  className="field-focus block w-full rounded-xl border border-white/10 bg-zinc-900/80 px-3 py-2.5 text-sm text-zinc-100 outline-none placeholder:text-zinc-600"
                />
              </label>
              <label className="block space-y-1.5">
                <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">Назва, якщо хочеш</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Наприклад, робота"
                  maxLength={120}
                  className="field-focus block w-full rounded-xl border border-white/10 bg-zinc-900/80 px-3 py-2.5 text-sm text-zinc-100 outline-none placeholder:text-zinc-600"
                />
              </label>
              <p className="text-xs leading-relaxed text-zinc-500">
                У Google Calendar відкрий налаштування потрібного календаря і скопіюй секретну адресу у форматі iCal.
              </p>
              {error && <p className="text-sm text-rose-400">{error}</p>}
              <button
                type="submit"
                disabled={submitting || !url.trim()}
                className="w-full rounded-2xl bg-gradient-to-r from-violet-600 to-fuchsia-500 py-3.5 text-sm font-semibold text-white shadow-[0_0_24px_rgba(168,85,247,0.35)] disabled:opacity-40"
              >
                {submitting ? "Підключаю…" : "Підʼєднати"}
              </button>

              {feeds.length > 0 && (
                <ul className="space-y-2">
                  {feeds.map((feed) => (
                    <li key={feed.id} className="flex items-center gap-3 rounded-2xl border border-white/10 px-3 py-2.5">
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-zinc-100">{feed.name}</p>
                        <p className="truncate text-xs text-zinc-500">
                          {feed.host}
                          {feed.last_error ? ` · ${feed.last_error}` : ` · ${feed.event_count} подій`}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => void remove(feed.id)}
                        className="shrink-0 text-xs font-medium text-zinc-400 hover:text-rose-300"
                      >
                        Прибрати
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </form>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}
