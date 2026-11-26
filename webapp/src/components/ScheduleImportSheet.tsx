"use client";

import { AnimatePresence } from "framer-motion";
import { Check, FileText, Loader2, X } from "lucide-react";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import { ChoiceChip, SegmentedControl } from "@/components/SegmentedControl";
import { importApi, USE_MOCKS } from "@/lib/api";
import { cn } from "@/lib/cn";
import { type Assignee, useCouple } from "@/lib/couple";
import { addDays, dateKey, formatDayKey, formatTime, todayKey, viennaToDate } from "@/lib/date";
import { haptic } from "@/lib/telegram";
import { CATEGORIES, type Category, type ScheduleEvent, type SchedulePreview } from "@/lib/types";

import { Reveal } from "./Reveal";
import { SheetBackdrop, SheetPanel } from "./Sheet";

type Step = "pick" | "reading" | "preview" | "saving" | "done";

const REMINDERS: { id: string; label: string; minutes: number | null }[] = [
  { id: "off", label: "Вимк.", minutes: null },
  { id: "0", label: "У момент", minutes: 0 },
  { id: "15", label: "15 хв", minutes: 15 },
  { id: "30", label: "30 хв", minutes: 30 },
  { id: "60", label: "1 год", minutes: 60 },
];

interface ScheduleImportSheetProps {
  open: boolean;
  onClose: () => void;
  onImported: () => void;
}

/** Timetable PDF → preview → pick who it is for → add to the planner (and Google). */
export function ScheduleImportSheet({ open, onClose, onImported }: ScheduleImportSheetProps) {
  const titleId = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const { partnerName } = useCouple();
  const [step, setStep] = useState<Step>("pick");
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<SchedulePreview | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [assignee, setAssignee] = useState<Assignee>("me");
  const [category, setCategory] = useState<Category | null>("навчання");
  const [reminder, setReminder] = useState("15");
  const [result, setResult] = useState<{ created: number; skipped: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    setStep("pick");
    setError(null);
    setPreview(null);
    setSelected(new Set());
    setAssignee("me");
    setCategory("навчання");
    setReminder("15");
    setResult(null);
  }, [open]);

  const groups = useMemo(() => {
    const byDay = new Map<string, { event: ScheduleEvent; index: number }[]>();
    preview?.events.forEach((event, index) => {
      const key = dateKey(event.start);
      byDay.set(key, [...(byDay.get(key) ?? []), { event, index }]);
    });
    return [...byDay.entries()];
  }, [preview]);

  async function readFile(file: File) {
    setError(null);
    if (file.type && file.type !== "application/pdf") {
      setError("Обери PDF-файл.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("PDF завеликий: до 10 МБ.");
      return;
    }
    setStep("reading");
    try {
      const data = USE_MOCKS ? demoPreview() : await importApi.preview(await toBase64(file), file.name);
      if (!data.events.length) {
        setError("Не знайшов у файлі занять із датою чи днем тижня та часом.");
        setStep("pick");
        return;
      }
      setPreview(data);
      setSelected(new Set(data.events.map((_, index) => index)));
      setStep("preview");
      haptic.notify("success");
    } catch (err) {
      haptic.notify("error");
      setError(err instanceof Error ? err.message : "Не вдалося прочитати файл");
      setStep("pick");
    }
  }

  async function commit() {
    if (!preview) return;
    const events = preview.events.filter((_, index) => selected.has(index));
    if (!events.length) return;
    setStep("saving");
    try {
      const outcome = USE_MOCKS
        ? { created: events.length, skipped: 0 }
        : await importApi.commit({
            events,
            assignee,
            category,
            remind_before_minutes: REMINDERS.find((r) => r.id === reminder)?.minutes ?? null,
            title: preview.title,
          });
      setResult(outcome);
      setStep("done");
      haptic.notify("success");
      onImported();
    } catch (err) {
      haptic.notify("error");
      setError(err instanceof Error ? err.message : "Не вдалося додати події");
      setStep("preview");
    }
  }

  function toggle(index: number) {
    haptic.selection();
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  }

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-labelledby={titleId}>
          <SheetBackdrop onClose={onClose} />
          <SheetPanel>
            <div className="mx-auto mb-2 mt-3 h-1 w-10 rounded-full bg-white/15" />
            <div className="space-y-4 px-4 pb-5 sm:px-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 id={titleId} className="flex items-center gap-2 text-lg font-semibold tracking-tight text-zinc-100">
                    <FileText className="size-4 text-purple-300" />
                    {preview?.title || "Розклад з PDF"}
                  </h2>
                  <p className="mt-0.5 text-sm leading-snug text-zinc-500">
                    {step === "preview" || step === "saving"
                      ? `Знайшов ${events(preview?.events.length ?? 0)}. Зніми галочки з зайвих.`
                      : "Пари, зміни, гуртки — я прочитаю файл і розкладу все по днях."}
                  </p>
                </div>
                <button
                  type="button"
                  aria-label="Закрити"
                  onClick={onClose}
                  className="flex size-9 shrink-0 items-center justify-center rounded-full border border-white/10 bg-zinc-900 text-zinc-400 hover:text-zinc-100"
                >
                  <X className="size-4" />
                </button>
              </div>

              <input
                ref={fileRef}
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  if (file) void readFile(file);
                }}
              />

              {step === "pick" && (
                <button
                  type="button"
                  onClick={() => fileRef.current?.click()}
                  className="flex w-full flex-col items-center gap-2 rounded-2xl border border-dashed border-purple-500/40 bg-purple-500/10 px-4 py-8 text-center text-sm text-zinc-300"
                >
                  <FileText className="size-7 text-purple-300" />
                  <span className="font-medium text-zinc-100">Обрати PDF з розкладом</span>
                  <span className="text-xs text-zinc-500">до 10 МБ · тижневі пари розгорну до кінця семестру (макс. 16 тижнів)</span>
                </button>
              )}

              {step === "reading" && (
                <div className="flex flex-col items-center gap-3 py-10 text-sm text-zinc-400">
                  <Loader2 className="size-7 animate-spin text-purple-300" />
                  Читаю розклад… це може зайняти до хвилини
                </div>
              )}

              <Reveal show={Boolean(error)}>
                <p className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-3 py-2 text-sm text-rose-300">{error}</p>
              </Reveal>

              {(step === "preview" || step === "saving") && preview && (
                <>
                  <div className="flex items-center justify-between text-xs text-zinc-500">
                    <span>
                      Обрано {selected.size} з {preview.events.length}
                    </span>
                    <button
                      type="button"
                      className="font-medium text-purple-300"
                      onClick={() =>
                        setSelected(
                          selected.size === preview.events.length
                            ? new Set()
                            : new Set(preview.events.map((_, index) => index)),
                        )
                      }
                    >
                      {selected.size === preview.events.length ? "Зняти всі" : "Обрати всі"}
                    </button>
                  </div>

                  <div className="max-h-[38dvh] space-y-3 overflow-y-auto rounded-2xl border border-white/10 bg-white/[0.04] p-2">
                    {groups.map(([day, items]) => (
                      <section key={day} className="space-y-1">
                        <h3 className="px-1 pt-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-zinc-500">
                          {formatDayKey(day)}
                        </h3>
                        {items.map(({ event, index }) => {
                          const on = selected.has(index);
                          return (
                            <button
                              key={index}
                              type="button"
                              onClick={() => toggle(index)}
                              className={cn(
                                "flex w-full items-start gap-2.5 rounded-xl px-2 py-1.5 text-left",
                                on ? "text-zinc-100" : "text-zinc-500",
                              )}
                            >
                              <span
                                className={cn(
                                  "mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-md border transition-colors",
                                  on ? "border-transparent bg-purple-500 text-white" : "border-zinc-600",
                                )}
                              >
                                {on && <Check className="size-3.5" strokeWidth={3} />}
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className={cn("block truncate text-sm", !on && "line-through")}>{event.title}</span>
                                <span className="block truncate text-xs text-zinc-500">
                                  {formatTime(event.start)}–{formatTime(event.end)}
                                  {event.description ? ` · ${event.description}` : ""}
                                </span>
                              </span>
                            </button>
                          );
                        })}
                      </section>
                    ))}
                  </div>

                  <fieldset className="min-w-0 space-y-2">
                    <legend className="text-xs font-medium uppercase tracking-wider text-zinc-500">Хто робить</legend>
                    <SegmentedControl
                      fullWidth
                      anchored
                      layoutId="import-assignee"
                      value={assignee}
                      options={[
                        { id: "me", label: "Я" },
                        { id: "partner", label: partnerName },
                        { id: "shared", label: "Разом ⚡️" },
                      ]}
                      onChange={(next) => {
                        haptic.selection();
                        setAssignee(next);
                      }}
                    />
                  </fieldset>

                  <fieldset className="min-w-0 space-y-2">
                    <legend className="text-xs font-medium uppercase tracking-wider text-zinc-500">Тег</legend>
                    <div className="flex flex-wrap gap-1.5">
                      {CATEGORIES.map((tag) => (
                        <ChoiceChip
                          key={tag}
                          layoutId="import-tag"
                          anchored
                          active={category === tag}
                          onClick={() => {
                            haptic.selection();
                            setCategory(category === tag ? null : tag);
                          }}
                        >
                          #{tag}
                        </ChoiceChip>
                      ))}
                    </div>
                  </fieldset>

                  <fieldset className="min-w-0 space-y-2">
                    <legend className="text-xs font-medium uppercase tracking-wider text-zinc-500">Нагадати до кожної</legend>
                    <div className="flex flex-wrap gap-1.5">
                      {REMINDERS.map((item) => (
                        <ChoiceChip
                          key={item.id}
                          layoutId="import-reminder"
                          anchored
                          active={reminder === item.id}
                          onClick={() => {
                            haptic.selection();
                            setReminder(item.id);
                          }}
                        >
                          {item.label}
                        </ChoiceChip>
                      ))}
                    </div>
                  </fieldset>

                  <button
                    type="button"
                    disabled={step === "saving" || selected.size === 0}
                    onClick={() => void commit()}
                    className="choice-fill w-full rounded-2xl py-3.5 text-sm font-semibold text-white disabled:opacity-40"
                  >
                    {step === "saving" ? "Додаю…" : `Додати ${events(selected.size)}`}
                  </button>
                </>
              )}

              {step === "done" && result && (
                <div className="space-y-3 py-4 text-center">
                  <p className="text-base font-medium text-zinc-100">✅ Додано {events(result.created)}</p>
                  <p className="text-sm text-zinc-500">
                    {result.skipped ? `${result.skipped} вже були в планері — пропустив. ` : ""}
                    У Google Calendar вони з'являться за хвилину.
                  </p>
                  <button
                    type="button"
                    onClick={onClose}
                    className="w-full rounded-2xl border border-white/10 py-3 text-sm font-semibold text-zinc-100"
                  >
                    Готово
                  </button>
                </div>
              )}
            </div>
          </SheetPanel>
        </div>
      )}
    </AnimatePresence>
  );
}

function toBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("Не вдалося відкрити файл"));
    reader.readAsDataURL(file);
  });
}

/** Demo build: a typical university week, so the flow can be tried without the API. */
function demoPreview(): SchedulePreview {
  const today = todayKey();
  const lessons = [
    { day: 0, start: "08:30", end: "10:05", title: "Вища математика", description: "ауд. 312 · лекція" },
    { day: 0, start: "10:25", end: "12:00", title: "Програмування", description: "ауд. 105 · практика" },
    { day: 1, start: "12:20", end: "13:55", title: "Англійська мова", description: "ауд. 220" },
    { day: 3, start: "08:30", end: "10:05", title: "Фізика", description: "лаб. 2" },
    { day: 7, start: "08:30", end: "10:05", title: "Вища математика", description: "ауд. 312 · лекція" },
  ];
  return {
    title: "Розклад КН-21",
    events: lessons.map((lesson) => {
      const key = addDays(today, lesson.day + 1);
      return {
        title: lesson.title,
        start: viennaToDate(key, lesson.start).toISOString(),
        end: viennaToDate(key, lesson.end).toISOString(),
        description: lesson.description,
      };
    }),
  };
}

/** 1 подію / 2 події / 5 подій. */
function events(count: number): string {
  const mod10 = count % 10;
  const mod100 = count % 100;
  const word = mod10 === 1 && mod100 !== 11 ? "подію" : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14) ? "події" : "подій";
  return `${count} ${word}`;
}
