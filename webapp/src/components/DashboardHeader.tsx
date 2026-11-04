"use client";

import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import { useEffect, useState } from "react";

import { formatLongToday, greeting } from "@/lib/date";

interface DashboardHeaderProps {
  firstName: string | null;
  done: number;
  total: number;
}

export function DashboardHeader({ firstName, done, total }: DashboardHeaderProps) {
  // Time-dependent text is computed after mount to avoid hydration mismatches.
  const [labels, setLabels] = useState<{ hello: string; today: string } | null>(null);
  useEffect(() => setLabels({ hello: greeting(), today: formatLongToday() }), []);

  const percent = total === 0 ? 0 : Math.round((done / total) * 100);
  const allDone = total > 0 && done === total;

  return (
    <header className="space-y-5">
      <div className="space-y-1">
        <p className="h-5 text-sm text-zinc-400">{labels?.today}</p>
        <h1 className="h-8 text-[26px] font-semibold leading-8 tracking-tight text-zinc-100">
          {labels && (
            <>
              {labels.hello}
              {firstName && <span className="text-zinc-400">, {firstName}</span>}
            </>
          )}
        </h1>
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
            {allDone && <Sparkles className="size-4 text-fuchsia-400" />}
            <motion.span
              key={percent}
              initial={{ opacity: 0, y: 4 }}
              animate={{ opacity: 1, y: 0 }}
              className="font-mono text-2xl font-semibold tabular-nums text-zinc-100"
            >
              {percent}%
            </motion.span>
          </div>
        </div>

        <div className="relative mt-4 h-2 overflow-hidden rounded-full bg-zinc-800/80">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-violet-600 to-fuchsia-500 shadow-[0_0_12px_rgba(192,38,211,0.55)]"
            initial={{ width: 0 }}
            animate={{ width: `${percent}%` }}
            transition={{ type: "spring", stiffness: 120, damping: 20 }}
          />
        </div>
      </section>
    </header>
  );
}
