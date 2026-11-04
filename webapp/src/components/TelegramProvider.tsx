"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { initTelegram, type TelegramWebApp } from "@/lib/telegram";

interface TelegramContextValue {
  webApp: TelegramWebApp | null;
  firstName: string | null;
  isReady: boolean;
}

const TelegramContext = createContext<TelegramContextValue>({
  webApp: null,
  firstName: null,
  isReady: false,
});

export function TelegramProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<TelegramContextValue>({ webApp: null, firstName: null, isReady: false });

  useEffect(() => {
    let cancelled = false;
    initTelegram()
      .then((webApp) => {
        if (cancelled) return;
        setValue({
          webApp,
          firstName: webApp?.initDataUnsafe?.user?.first_name ?? null,
          isReady: true,
        });
      })
      .catch(() => {
        if (!cancelled) setValue({ webApp: null, firstName: null, isReady: true });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <TelegramContext.Provider value={value}>{children}</TelegramContext.Provider>;
}

export function useTelegram() {
  return useContext(TelegramContext);
}
