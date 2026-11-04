import { addDays, todayKey, viennaToDate } from "./date";
import type { Task, TaskCreate } from "./types";

function at(dayOffset: number, time: string): string {
  return viennaToDate(addDays(todayKey(), dayOffset), time).toISOString();
}

function block(dayOffset: number, time: string, hours = 1) {
  const start = at(dayOffset, time);
  const end = new Date(new Date(start).getTime() + hours * 3_600_000).toISOString();
  return { start_time: start, end_time: end, deadline: end };
}

/** Built relative to "now", so the demo always has something for today. */
export function createMockTasks(): Task[] {
  const created = new Date().toISOString();
  return [
    {
      id: 1,
      title: "Підготувати презентацію для клієнта",
      description: "Слайди з метриками Q4 та roadmap",
      category: "робота",
      priority: "high",
      ...block(0, "15:00"),
      remind_at: at(0, "14:30"),
      google_event_id: "gcal-demo-1",
      sync_token: "demo-sync",
      is_completed: false,
      created_at: created,
    },
    {
      id: 2,
      title: "Ранкова пробіжка 5 км",
      description: null,
      category: "тренування",
      priority: "medium",
      ...block(0, "07:30"),
      remind_at: null,
      google_event_id: null,
      sync_token: null,
      is_completed: true,
      created_at: created,
    },
    {
      id: 3,
      title: "Пройти модуль з TypeScript generics",
      description: "Розділ 4: conditional types",
      category: "навчання",
      priority: "medium",
      ...block(0, "20:00"),
      remind_at: at(0, "19:45"),
      google_event_id: "gcal-demo-3",
      sync_token: "demo-sync",
      is_completed: false,
      created_at: created,
    },
    {
      id: 4,
      title: "Code review PR з авторизацією",
      description: null,
      category: "робота",
      priority: "low",
      ...block(0, "12:00"),
      remind_at: null,
      google_event_id: null,
      sync_token: null,
      is_completed: true,
      created_at: created,
    },
    {
      id: 5,
      title: "Силове тренування: спина + плечі",
      description: null,
      category: "тренування",
      priority: "medium",
      ...block(1, "18:30"),
      remind_at: at(1, "18:00"),
      google_event_id: "gcal-demo-5",
      sync_token: "demo-sync",
      is_completed: false,
      created_at: created,
    },
    {
      id: 6,
      title: "Відправити звіт за місяць",
      description: "Не забути додати таблицю витрат",
      category: "робота",
      priority: "high",
      ...block(3, "10:00"),
      remind_at: at(3, "09:00"),
      google_event_id: "gcal-demo-6",
      sync_token: "demo-sync",
      is_completed: false,
      created_at: created,
    },
    {
      id: 7,
      title: "Прочитати розділ «Designing Data-Intensive Applications»",
      description: null,
      category: "навчання",
      priority: "low",
      ...block(5, "21:00"),
      remind_at: null,
      google_event_id: null,
      sync_token: null,
      is_completed: false,
      created_at: created,
    },
  ];
}

let mockId = 1000;

export function buildMockTask(data: TaskCreate): Task {
  return {
    id: ++mockId,
    title: data.title,
    description: data.description ?? null,
    category: data.category ?? null,
    priority: data.priority ?? "medium",
    deadline: data.deadline ?? data.end_time ?? null,
    remind_at: data.remind_at ?? null,
    start_time: data.start_time ?? null,
    end_time: data.end_time ?? null,
    google_event_id: null,
    sync_token: null,
    is_completed: false,
    created_at: new Date().toISOString(),
  };
}
