"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { initTelegram, type TelegramWebApp } from "@/lib/telegram";
import { applyTheme } from "@/lib/theme";

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
        applyTheme(webApp?.initDataUnsafe?.user?.id);
        setValue({
          webApp,
          firstName: webApp?.initDataUnsafe?.user?.first_name ?? null,
          isReady: true,
        });
      })
      .catch(() => {
        if (cancelled) return;
        applyTheme(null);
        setValue({ webApp: null, firstName: null, isReady: true });
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
