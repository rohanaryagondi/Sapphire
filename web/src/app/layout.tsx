import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sapphire — CNS drug-discovery decision firm",
  description:
    "Sapphire convenes a two-bucket agentic firm: a cited fact dossier, then a persona roundtable, then a synthesis. Built by Quiver Bioscience.",
};

export const viewport: Viewport = {
  themeColor: "#08090a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="app-backdrop antialiased">
        <TooltipProvider delayDuration={250} skipDelayDuration={400}>
          {children}
        </TooltipProvider>
      </body>
    </html>
  );
}
