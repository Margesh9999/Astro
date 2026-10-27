import type { Metadata } from "next";
import { Geist, Geist_Mono, Marcellus, Rozha_One } from "next/font/google";
import "./globals.css";
import { Toaster } from "@/components/ui/toaster";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

// Classical serif for headings — pairs well with the pastel Vedic theme
const marcellus = Marcellus({
  variable: "--font-display",
  weight: "400",
  subsets: ["latin"],
});

// Devanagari-inspired display face for the brand mark
const rozhaOne = Rozha_One({
  variable: "--font-brand",
  weight: "400",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AstroTrader — Vedic Jyotisha × Market Data",
  description:
    "Educational exploration of Swiss Ephemeris planetary positions, North Indian kundali charts and historical market correlations. Not financial advice.",
  keywords: ["astrotrader", "vedic", "kundali", "north indian chart", "swiss ephemeris", "market data", "educational"],
  authors: [{ name: "AstroTrader" }],
  icons: {
    icon: "https://z-cdn.chatglm.cn/z-ai/static/logo.svg",
  },
  openGraph: {
    title: "AstroTrader — Vedic Jyotisha × Market Data",
    description: "Swiss Ephemeris × North Indian kundali × market data — educational exploration only.",
    siteName: "AstroTrader",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} ${marcellus.variable} ${rozhaOne.variable} antialiased bg-background text-foreground`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
