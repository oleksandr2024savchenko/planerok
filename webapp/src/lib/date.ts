export const TIME_ZONE = "Europe/Vienna";

const dateKeyFormat = new Intl.DateTimeFormat("en-CA", {
  timeZone: TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

const timeFormat = new Intl.DateTimeFormat("uk-UA", {
  timeZone: TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const shortDayFormat = new Intl.DateTimeFormat("uk-UA", {
  timeZone: TIME_ZONE,
  day: "numeric",
  month: "short",
});

const longDayFormat = new Intl.DateTimeFormat("uk-UA", {
  timeZone: TIME_ZONE,
  weekday: "long",
  day: "numeric",
  month: "long",
});

const partsFormat = new Intl.DateTimeFormat("en-US", {
  timeZone: TIME_ZONE,
  hourCycle: "h23",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

/** `YYYY-MM-DD` of the given instant in Vienna. */
export function dateKey(value: Date | string): string {
  return dateKeyFormat.format(typeof value === "string" ? new Date(value) : value);
}

export function todayKey(): string {
  return dateKey(new Date());
}

export function addDays(key: string, days: number): string {
  const [y, m, d] = key.split("-").map(Number);
  const shifted = new Date(Date.UTC(y, m - 1, d + days));
  return shifted.toISOString().slice(0, 10);
}

function viennaOffsetMinutes(at: Date): number {
  const parts = Object.fromEntries(partsFormat.formatToParts(at).map((p) => [p.type, p.value]));
  const asUtc = Date.UTC(
    Number(parts.year),
    Number(parts.month) - 1,
    Number(parts.day),
    Number(parts.hour),
    Number(parts.minute),
    Number(parts.second),
  );
  return Math.round((asUtc - Math.floor(at.getTime() / 1000) * 1000) / 60000);
}

/** Converts a Vienna wall-clock date + `HH:mm` to a real instant (DST-aware). */
export function viennaToDate(key: string, time: string): Date {
  const [y, m, d] = key.split("-").map(Number);
  const [hh, mm] = time.split(":").map(Number);
  const naive = Date.UTC(y, m - 1, d, hh, mm);
  const firstGuess = naive - viennaOffsetMinutes(new Date(naive)) * 60000;
  return new Date(naive - viennaOffsetMinutes(new Date(firstGuess)) * 60000);
}

export function formatTime(iso: string): string {
  return timeFormat.format(new Date(iso));
}

export function formatDayKey(key: string): string {
  const today = todayKey();
  if (key === today) return "Сьогодні";
  if (key === addDays(today, 1)) return "Завтра";
  if (key === addDays(today, -1)) return "Вчора";
  return shortDayFormat.format(viennaToDate(key, "12:00"));
}

export function formatDay(iso: string): string {
  return formatDayKey(dateKey(iso));
}

export function formatLongToday(): string {
  const text = longDayFormat.format(new Date());
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function viennaHour(): number {
  return Number(partsFormat.formatToParts(new Date()).find((p) => p.type === "hour")?.value ?? 12);
}

export function greeting(): string {
  const hour = viennaHour();
  if (hour < 5) return "Доброї ночі";
  if (hour < 12) return "Доброго ранку";
  if (hour < 18) return "Доброго дня";
  return "Доброго вечора";
}
