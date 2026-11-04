import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { ReactNode } from "react";

import { TelegramProvider } from "@/components/TelegramProvider";

import "./globals.css";

export const metadata: Metadata = {
  title: "Planer",
  description: "Персональний планер у Telegram",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#09090B",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="uk" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="bg-zinc-950 font-sans text-zinc-100">
        <TelegramProvider>{children}</TelegramProvider>
      </body>
    </html>
  );
}
