import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";

import { Footer } from "@/components/footer";
import { Navbar } from "@/components/navbar";
import { Providers } from "@/components/providers";
import { API_SERVER_URL } from "@/lib/api";

import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  display: "swap",
});

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "Ahmedabad Startup Jobs — Real-time hiring intelligence for Gujarat startups",
    template: "%s · Ahmedabad Startup Jobs",
  },
  description:
    "Every Ahmedabad, Gandhinagar and GIFT City startup job in one place. Search verified openings by role, skill, experience and location — with the original application link and source on every listing.",
  keywords: [
    "Ahmedabad startup jobs",
    "Gujarat startup hiring",
    "GIFT City jobs",
    "Gandhinagar jobs",
    "startup internships India",
    "AI engineer jobs Ahmedabad",
    "freshers jobs Ahmedabad",
  ],
  authors: [{ name: "Ahmedabad Startup Jobs" }],
  openGraph: {
    type: "website",
    siteName: "Ahmedabad Startup Jobs",
    title: "Ahmedabad Startup Jobs",
    description:
      "Real-time startup hiring intelligence for Ahmedabad, Gandhinagar and GIFT City.",
  },
  twitter: {
    card: "summary_large_image",
    title: "Ahmedabad Startup Jobs",
    description:
      "Real-time startup hiring intelligence for Ahmedabad, Gandhinagar and GIFT City.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: { index: true, follow: true, "max-image-preview": "large" },
  },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1117" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${mono.variable} font-sans antialiased`}>
        <Providers>
          <div className="flex min-h-screen flex-col">
            <Navbar />
            <main className="flex-1">{children}</main>
            <Footer />
          </div>
        </Providers>
      </body>
    </html>
  );
}

export const revalidate = 300;

export async function generateStaticParams() {
  return [];
}

export const dynamicParams = true;

export async function fetchFromApi<T>(path: string, init?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(`${API_SERVER_URL}${path}`, {
      ...init,
      next: { revalidate: 300 },
      headers: { Accept: "application/json" },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}
