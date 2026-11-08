import type { Metadata } from "next";
import "./globals.css";

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
    <html lang="en" data-theme="light">
      <body className="antialiased">{children}</body>
    </html>
  );
}
