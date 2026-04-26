import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";

import { Toaster } from "@/components/ui/toaster";

import "./globals.css";

export const metadata: Metadata = {
  title: "LabSmith",
  description: "AI-powered lab hardware design",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="h-full antialiased">
        <head>
          <link
            rel="stylesheet"
            href="https://api.fontshare.com/v2/css?f[]=satoshi@400,500,600,700,800,900&display=swap"
          />
        </head>
        <body className="min-h-full flex flex-col bg-background text-foreground">
          {children}
          <Toaster />
        </body>
      </html>
    </ClerkProvider>
  );
}
