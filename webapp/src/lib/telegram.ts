import type TelegramWebAppSdk from "@twa-dev/sdk";

export type TelegramWebApp = typeof TelegramWebAppSdk;
type ImpactStyle = Parameters<TelegramWebApp["HapticFeedback"]["impactOccurred"]>[0];
type NotificationType = Parameters<TelegramWebApp["HapticFeedback"]["notificationOccurred"]>[0];

const SURFACE_COLOR = "#09090B";

let webApp: TelegramWebApp | null = null;

/** The SDK touches `window` on import, so it is loaded lazily on the client only. */
export async function initTelegram(): Promise<TelegramWebApp | null> {
  if (typeof window === "undefined") return null;
  if (webApp) return webApp;

  try {
    const { default: sdk } = await import("@twa-dev/sdk");
    webApp = sdk;
    safely(() => sdk.ready());
    safely(() => sdk.expand());
    if (sdk.isVersionAtLeast("6.1")) {
      safely(() => sdk.setHeaderColor(SURFACE_COLOR));
      safely(() => sdk.setBackgroundColor(SURFACE_COLOR));
    }
    if (sdk.isVersionAtLeast("7.7")) {
      safely(() => sdk.disableVerticalSwipes());
    }
    return sdk;
  } catch {
    return null;
  }
}

export function getInitData(): string {
  return webApp?.initData ?? "";
}

export const haptic = {
  impact(style: ImpactStyle = "medium") {
    safely(() => webApp?.HapticFeedback?.impactOccurred?.(style));
  },
  notify(type: NotificationType) {
    safely(() => webApp?.HapticFeedback?.notificationOccurred?.(type));
  },
  selection() {
    safely(() => webApp?.HapticFeedback?.selectionChanged?.());
  },
};

/** Outside Telegram (or on old clients) the SDK throws on unsupported methods. */
function safely(fn: () => unknown) {
  try {
    fn();
  } catch {
    // Not supported in this environment.
  }
}
