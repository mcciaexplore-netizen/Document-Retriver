import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "MCCIA Enterprise Document Search",
  description:
    "Private Enterprise Search, Evidence Retrieval & Audit. Search your business files. Find exact evidence. Verify every result.",
  robots: { index: false, follow: false },
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
