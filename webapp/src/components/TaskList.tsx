"use client";

import { AnimatePresence, motion } from "framer-motion";
import type { ReactNode } from "react";

import { groupByDate, isOverdue, type FilterId } from "@/lib/filters";
import { EASE, GLIDE } from "@/lib/motion";
import type { Task } from "@/lib/types";

import { TaskCard } from "./TaskCard";

interface TaskListProps {
  tasks: Task[];
  filter: FilterId;
  onToggle: (id: number) => void;
  onOpen?: (id: number) => void;
}

export function TaskList({ tasks, filter, onToggle, onOpen }: TaskListProps) {
  if (filter === "today") {
    const overdue = tasks.filter((task) => isOverdue(task));
    const due = tasks.filter((task) => !isOverdue(task));
    return (
      <div className="space-y-6">
        {overdue.length > 0 && (
          <Section title="Прострочені" accent>
            <Cards tasks={overdue} onToggle={onToggle} onOpen={onOpen} />
          </Section>
        )}
        {due.length > 0 && (
          <Section title={overdue.length > 0 ? "Сьогодні" : undefined}>
            <Cards tasks={due} onToggle={onToggle} onOpen={onOpen} />
          </Section>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {groupByDate(tasks).map((group) => (
        <Section key={group.key} title={group.label}>
          <Cards tasks={group.tasks} onToggle={onToggle} onOpen={onOpen} />
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
  onToggle,
  onOpen,
}: {
  tasks: Task[];
  onToggle: (id: number) => void;
  onOpen?: (id: number) => void;
}) {
  return (
    <ul className="space-y-2.5">
      <AnimatePresence initial={false} mode="popLayout">
        {tasks.map((task) => (
          <motion.li
            key={task.id}
            layout
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ layout: GLIDE, opacity: { duration: 0.3, ease: EASE } }}
          >
            <TaskCard task={task} onToggle={onToggle} onOpen={onOpen} />
          </motion.li>
        ))}
      </AnimatePresence>
    </ul>
  );
}
