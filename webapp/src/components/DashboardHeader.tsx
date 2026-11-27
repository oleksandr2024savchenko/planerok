"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { formatLongToday, greeting } from "@/lib/date";
import { EASE } from "@/lib/motion";

import { Flower } from "./Flower";

interface DashboardHeaderProps {
  firstName: string | null;
  done: number;
  total: number;
  settings?: ReactNode;
}

export function DashboardHeader({ firstName, done, total, settings }: DashboardHeaderProps) {
  // Time-dependent text is computed after mount to avoid hydration mismatches.
  const [labels, setLabels] = useState<{ hello: string; today: string } | null>(null);
  useEffect(() => setLabels({ hello: greeting(), today: formatLongToday() }), []);

  const percent = total === 0 ? 0 : Math.round((done / total) * 100);
  const allDone = total > 0 && done === total;

  return (
    <header className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="h-5 text-sm text-zinc-400">{labels?.today}</p>
          <h1 className="text-[26px] font-semibold leading-8 tracking-tight text-zinc-100">
            {labels && (
              <>
                {labels.hello}
                {firstName && <span className="text-zinc-400">, {firstName}</span>}
                <Flower className="pink-only ml-1.5 size-7 align-[-5px] [animation:flower-pop_0.6s_ease-out_both]" />
              </>
            )}
          </h1>
        </div>
        {settings}
      </div>

      <section className="relative overflow-hidden rounded-2xl border border-white/5 bg-zinc-900/60 p-4 backdrop-blur-xl">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-purple-600/20 via-violet-600/5 to-transparent" />

        <div className="relative flex items-end justify-between">
          <div>
            <p className="text-xs font-medium uppercase tracking-wider text-zinc-400">Прогрес на сьогодні</p>
            <p className="mt-1 text-sm text-zinc-300">
              {total === 0
                ? "На сьогодні задач немає"
                : allDone
                  ? "Усе виконано — так тримати!"
                  : `Виконано ${done} з ${total}`}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            {allDone && (
              <>
                <Sparkles className="not-pink size-4 text-fuchsia-400" />
                <Flower className="pink-only size-5" />
              </>
            )}
            <motion.span
              key={percent}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.25, ease: EASE }}
              className="font-mono text-2xl font-semibold tabular-nums text-zinc-100"
            >
              {percent}%
            </motion.span>
          </div>
        </div>

        <div className="relative mt-4">
          <div className="h-2 overflow-hidden rounded-full bg-zinc-800/80">
            <motion.div
              className="h-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500 shadow-[0_0_12px_rgba(192,38,211,0.55)]"
              initial={{ width: 0 }}
              animate={{ width: `${percent}%` }}
              transition={{ duration: 0.55, ease: EASE }}
            />
          </div>
          {/* Pink theme: a little flower rides the tip of the progress bar. */}
          <div className="pink-only">
            <motion.div
              className="pointer-events-none absolute top-1/2 size-6 -translate-x-1/2 -translate-y-1/2 drop-shadow-[0_0_6px_rgb(255_46_151/0.6)]"
              initial={{ left: "0%", rotate: 0 }}
              animate={{ left: `${Math.max(percent, 2)}%`, rotate: percent * 3.6 }}
              transition={{ duration: 0.55, ease: EASE }}
            >
              <Flower className="size-full" />
            </motion.div>
          </div>
        </div>
      </section>
    </header>
  );
}
