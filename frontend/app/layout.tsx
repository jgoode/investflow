import type { Metadata } from "next";
import "./globals.css";

import { DEFAULT_THEME } from "./theme";

export const metadata: Metadata = {
  title: "InvestFlow",
  description: "Personal accounting — ledger, investments, reports",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme={DEFAULT_THEME} suppressHydrationWarning>
      <body className="antialiased bg-base-100 text-base-content">{children}</body>
    </html>
  );
}
