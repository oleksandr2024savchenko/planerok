"use client";

import { ListTodo } from "lucide-react";

import type { FilterId } from "@/lib/filters";

const COPY: Record<string, { title: string; hint: string }> = {
  today: { title: "На сьогодні все чисто", hint: "Додай задачу — або насолоджуйся вікном спокою." },
  scheduled: { title: "Немає запланованих задач", hint: "Майбутні дедлайни з’являться тут." },
  all: { title: "Поки що порожньо", hint: "Натисни + і запиши першу задачу." },
};

interface EmptyStateProps {
  filter: FilterId;
  onAdd: () => void;
}

export function EmptyState({ filter, onAdd }: EmptyStateProps) {
  const copy = COPY[filter] ?? {
    title: "Немає задач у цій категорії",
    hint: "Зміни фільтр або додай нову задачу з потрібним тегом.",
  };

  return (
    <div className="flex flex-col items-center px-6 py-16 text-center">
      <div className="mb-4 flex size-14 items-center justify-center rounded-2xl border border-purple-500/20 bg-purple-500/10 shadow-[0_0_24px_rgba(168,85,247,0.18)]">
        <ListTodo className="size-6 text-purple-300" />
      </div>
      <h2 className="text-base font-medium text-zinc-100">{copy.title}</h2>
      <p className="mt-1 max-w-[240px] text-sm leading-relaxed text-zinc-500">{copy.hint}</p>
      <button
        type="button"
        onClick={onAdd}
        className="mt-5 rounded-full border border-purple-500/30 bg-purple-500/10 px-4 py-2 text-sm font-medium text-purple-200 transition hover:border-purple-500/50 hover:bg-purple-500/15"
      >
        Додати задачу
      </button>
    </div>
  );
}
