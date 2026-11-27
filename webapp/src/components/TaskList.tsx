"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

import { groupByDate, isOverdue, type FilterId } from "@/lib/filters";
import type { Space, Task } from "@/lib/types";

import { TaskCard } from "./TaskCard";

interface TaskListProps {
  tasks: Task[];
  filter: FilterId;
  /** Present when the list mixes spaces, so each card shows its space. */
  spaces?: Map<number, Space> | null;
  onToggle: (id: number) => void;
}

export function TaskList({ tasks, filter, spaces = null, onToggle }: TaskListProps) {
  if (filter === "today") {
    const overdue = tasks.filter((task) => isOverdue(task));
    const due = tasks.filter((task) => !isOverdue(task));
    return (
      <div className="space-y-6">
        {overdue.length > 0 && (
          <Section title="Прострочені" accent>
            <Cards tasks={overdue} spaces={spaces} onToggle={onToggle} />
          </Section>
        )}
        {due.length > 0 && (
          <Section title={overdue.length > 0 ? "Сьогодні" : undefined}>
            <Cards tasks={due} spaces={spaces} onToggle={onToggle} />
          </Section>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {groupByDate(tasks).map((group) => (
        <Section key={group.key} title={group.label}>
          <Cards tasks={group.tasks} spaces={spaces} onToggle={onToggle} />
        </Section>
      ))}
    </div>
  );
}

function Section({
  title,
  accent,
  children,
}: {
  title?: string;
  accent?: boolean;
  children: ReactNode;
}) {
  return (
    <section className="space-y-2.5">
      {title && (
        <h2
          className={
            accent
              ? "text-[11px] font-semibold uppercase tracking-[0.16em] text-rose-400/90"
              : "text-[11px] font-semibold uppercase tracking-[0.16em] text-zinc-500"
          }
        >
          {title}
        </h2>
      )}
      {children}
    </section>
  );
}

function Cards({
  tasks,
  spaces,
  onToggle,
}: {
  tasks: Task[];
  spaces: Map<number, Space> | null;
  onToggle: (id: number) => void;
}) {
  return (
    <ul className="space-y-2.5">
      <AnimatePresence initial={false}>
        {tasks.map((task) => (
          <motion.li
            key={task.id}
            layout
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.98 }}
            transition={{ type: "spring", stiffness: 380, damping: 30 }}
          >
            <TaskCard task={task} space={spaces?.get(task.space_id) ?? null} onToggle={onToggle} />
          </motion.li>
        ))}
      </AnimatePresence>
    </ul>
  );
}
