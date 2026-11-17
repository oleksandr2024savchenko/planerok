"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

import { initTelegram, setTelegramColors, type TelegramWebApp } from "@/lib/telegram";
import { applyTheme, type Theme } from "@/lib/theme";

interface TelegramContextValue {
  webApp: TelegramWebApp | null;
  firstName: string | null;
  isReady: boolean;
  theme: Theme;
}

const TelegramContext = createContext<TelegramContextValue>({
  webApp: null,
  firstName: null,
  isReady: false,
  theme: "purple",
});

export function TelegramProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<TelegramContextValue>({
    webApp: null,
    firstName: null,
    isReady: false,
    theme: "purple",
  });

  useEffect(() => {
    let cancelled = false;
    initTelegram()
      .then((webApp) => {
        if (cancelled) return;
        const theme = applyTheme(webApp?.initDataUnsafe?.user?.id);
        if (theme === "pink") setTelegramColors(PINK_SURFACE);
        setValue({
          theme,
          webApp,
          firstName: webApp?.initDataUnsafe?.user?.first_name ?? null,
          isReady: true,
        });
      })
      .catch(() => {
        if (cancelled) return;
        const theme = applyTheme(null);
        setValue({ webApp: null, firstName: null, isReady: true, theme });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return <TelegramContext.Provider value={value}>{children}</TelegramContext.Provider>;
}

/** Matches --void of the pink theme, so Telegram's header blends into the page. */
const PINK_SURFACE = "#FFF0F7";

export function useTelegram() {
  return useContext(TelegramContext);
}
