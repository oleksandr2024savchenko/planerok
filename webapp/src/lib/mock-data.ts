import { addDays, todayKey, viennaToDate } from "./date";
import type { Task, TaskCreate } from "./types";

function at(dayOffset: number, time: string): string {
  return viennaToDate(addDays(todayKey(), dayOffset), time).toISOString();
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
      deadline: at(0, "15:00"),
      remind_at: at(0, "14:30"),
      is_completed: false,
      created_at: created,
    },
    {
      id: 2,
      title: "Ранкова пробіжка 5 км",
      description: null,
      category: "тренування",
      priority: "medium",
      deadline: at(0, "07:30"),
      remind_at: null,
      is_completed: true,
      created_at: created,
    },
    {
      id: 3,
      title: "Пройти модуль з TypeScript generics",
      description: "Розділ 4: conditional types",
      category: "навчання",
      priority: "medium",
      deadline: at(0, "20:00"),
      remind_at: at(0, "19:45"),
      is_completed: false,
      created_at: created,
    },
    {
      id: 4,
      title: "Code review PR з авторизацією",
      description: null,
      category: "робота",
      priority: "low",
      deadline: at(0, "12:00"),
      remind_at: null,
      is_completed: true,
      created_at: created,
    },
    {
      id: 5,
      title: "Силове тренування: спина + плечі",
      description: null,
      category: "тренування",
      priority: "medium",
      deadline: at(1, "18:30"),
      remind_at: at(1, "18:00"),
      is_completed: false,
      created_at: created,
    },
    {
      id: 6,
      title: "Відправити звіт за місяць",
      description: "Не забути додати таблицю витрат",
      category: "робота",
      priority: "high",
      deadline: at(3, "10:00"),
      remind_at: at(3, "09:00"),
      is_completed: false,
      created_at: created,
    },
    {
      id: 7,
      title: "Прочитати розділ «Designing Data-Intensive Applications»",
      description: null,
      category: "навчання",
      priority: "low",
      deadline: at(5, "21:00"),
      remind_at: null,
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
    deadline: data.deadline ?? null,
    remind_at: data.remind_at ?? null,
    is_completed: false,
    created_at: new Date().toISOString(),
  };
}
