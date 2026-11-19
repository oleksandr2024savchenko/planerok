import { assigneeOf } from "./couple";
import { dateKey, formatDayKey, todayKey } from "./date";
import { CATEGORIES, type Category, type Priority, type Task } from "./types";

export type FilterId = "today" | "scheduled" | "all" | `tag:${Category}`;
export type AudienceId = "mine" | "shared" | "all";

export const AUDIENCES: { id: AudienceId; label: string }[] = [
  { id: "mine", label: "Мої" },
  { id: "shared", label: "Спільні ⚡️" },
  { id: "all", label: "Усі" },
];

/** «Мої» are tasks I do myself; ones I gave to the partner show only under «Усі». */
export function matchesAudience(task: Task, audience: AudienceId, meId: number | null = null): boolean {
  if (audience === "shared") return Boolean(task.is_shared);
  if (audience === "mine") return assigneeOf(task, meId) === "me";
  return true;
}

export interface FilterOption {
  id: FilterId;
  label: string;
}

export const FILTERS: FilterOption[] = [
  { id: "today", label: "Сьогодні" },
  { id: "scheduled", label: "Заплановані" },
  { id: "all", label: "Усі" },
  ...CATEGORIES.map((category) => ({ id: `tag:${category}` as const, label: `#${category}` })),
];

function scheduleStamp(task: Task): string | null {
  return task.start_time ?? task.deadline;
}

export function isDueToday(task: Task, today = todayKey()): boolean {
  const stamp = scheduleStamp(task);
  return stamp !== null && dateKey(stamp) === today;
}

export function isOverdue(task: Task, today = todayKey()): boolean {
  if (task.read_only) return false;
  const stamp = scheduleStamp(task);
  return !task.is_completed && stamp !== null && dateKey(stamp) < today;
}

export function matchesFilter(task: Task, filter: FilterId, today = todayKey()): boolean {
  switch (filter) {
    case "today":
      return isDueToday(task, today) || isOverdue(task, today);
    case "scheduled": {
      const stamp = scheduleStamp(task);
      return stamp !== null && dateKey(stamp) > today;
    }
    case "all":
      return true;
    default:
      return task.category === filter.slice("tag:".length);
  }
}

const PRIORITY_WEIGHT: Record<Priority, number> = { high: 0, medium: 1, low: 2 };

export function sortTasks(tasks: Task[]): Task[] {
  return [...tasks].sort((a, b) => {
    if (a.is_completed !== b.is_completed) return a.is_completed ? 1 : -1;
    if (a.deadline && b.deadline && a.deadline !== b.deadline) {
      return new Date(a.deadline).getTime() - new Date(b.deadline).getTime();
    }
    if (a.deadline !== b.deadline) return a.deadline ? -1 : 1;
    return PRIORITY_WEIGHT[a.priority] - PRIORITY_WEIGHT[b.priority];
  });
}

/** My day: tasks I gave to the partner are theirs to finish, so they do not count here. */
export function todayProgress(tasks: Task[], meId: number | null = null): { done: number; total: number } {
  const today = todayKey();
  const relevant = tasks.filter((task) => isDueToday(task, today) && assigneeOf(task, meId) !== "partner");
  return { done: relevant.filter((task) => task.is_completed).length, total: relevant.length };
}

export function countByFilter(tasks: Task[]): Record<FilterId, number> {
  const today = todayKey();
  return Object.fromEntries(
    FILTERS.map((filter) => [filter.id, tasks.filter((task) => matchesFilter(task, filter.id, today)).length]),
  ) as Record<FilterId, number>;
}

export interface TaskGroup {
  key: string;
  label: string;
  tasks: Task[];
}

export function groupByDate(tasks: Task[]): TaskGroup[] {
  const buckets = new Map<string, Task[]>();
  for (const task of tasks) {
    const key = task.deadline ? dateKey(task.deadline) : "none";
    const list = buckets.get(key);
    if (list) list.push(task);
    else buckets.set(key, [task]);
  }

  return [...buckets.keys()]
    .sort((a, b) => {
      if (a === "none") return 1;
      if (b === "none") return -1;
      return a.localeCompare(b);
    })
    .map((key) => ({
      key,
      label: key === "none" ? "Без дати" : formatDayKey(key),
      tasks: buckets.get(key) ?? [],
    }));
}
