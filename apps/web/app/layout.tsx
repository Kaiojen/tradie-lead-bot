import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Tradie Lead Bot",
  description: "Automated Inbox for Australian tradies."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en-AU" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
