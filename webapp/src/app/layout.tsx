import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { ReactNode } from "react";

import { TelegramProvider } from "@/components/TelegramProvider";
import { FlowerDecor } from "@/components/FlowerDecor";
import { ThemeDecor } from "@/components/ThemeDecor";

import "./globals.css";

const THEME_BOOT = `try{var t=localStorage.getItem("planer:theme");if(t==="pink"||t==="violet")document.documentElement.dataset.theme=t}catch(e){}`;

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
  themeColor: "#12061f",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html
      lang="uk"
      data-theme="violet"
      suppressHydrationWarning
      className={`${GeistSans.variable} ${GeistMono.variable}`}
    >
      <head>
        {/* Paint the remembered theme before React starts, so the pink page never flashes violet. */}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT }} />
      </head>
      <body className="font-sans text-zinc-100">
        <ThemeDecor />
        <div className="pink-only">
          <FlowerDecor />
        </div>
        <TelegramProvider>{children}</TelegramProvider>
      </body>
    </html>
  );
}
