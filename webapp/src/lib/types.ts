export type Priority = "low" | "medium" | "high";
export type TaskStatus = "backlog" | "todo" | "doing" | "done";
export type SpaceKind = "personal" | "shared";
export type SpaceRole = "owner" | "editor" | "viewer";

/** Mirrors `SpaceRead`. The personal space is created automatically and cannot be deleted. */
export interface Space {
  id: number;
  name: string;
  color: string | null;
  icon: string | null;
  kind: SpaceKind;
  role: SpaceRole;
}

export interface SpaceInput {
  name?: string;
  color?: string | null;
  icon?: string | null;
}

/** Mirrors `TaskRead` from the backend. Datetimes are ISO strings with offset. */
export interface Task {
  id: number;
  space_id: number;
  created_by_id: number;
  title: string;
  description: string | null;
  category: string | null;
  priority: Priority;
  deadline: string | null;
  remind_at: string | null;
  start_time: string | null;
  end_time: string | null;
  google_event_id: string | null;
  sync_token: string | null;
  status: TaskStatus;
  is_completed: boolean;
  created_at: string;
  updated_at: string;
  /** RRULE subset, e.g. "FREQ=WEEKLY;BYDAY=MO". */
  recurrence_rule: string | null;
  recurrence_label: string | null;
  streak_current: number | null;
  streak_best: number | null;
}

export interface TaskCreate {
  title: string;
  space_id?: number | null;
  recurrence?: string | null;
  status?: TaskStatus;
  description?: string | null;
  category?: string | null;
  priority?: Priority;
  deadline?: string | null;
  remind_at?: string | null;
  start_time?: string | null;
  end_time?: string | null;
}

export interface CalendarStatus {
  connected: boolean;
  live: boolean;
  last_sync_at: string | null;
}

export type TaskUpdate = Partial<Omit<TaskCreate, "space_id">> & { space_id?: number; is_completed?: boolean };

export function canWrite(space: Space): boolean {
  return space.role !== "viewer";
}

export type TaskScope = "today" | "upcoming" | "all";

export const CATEGORIES = ["робота", "навчання", "тренування", "особисте"] as const;
export type Category = (typeof CATEGORIES)[number];

/** Morning digest settings; `digest_time` is "HH:MM" in the user's timezone. */
export interface NotificationPrefs {
  digest_enabled: boolean;
  digest_time: string;
}
