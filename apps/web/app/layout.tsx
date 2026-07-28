import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "RootsVida TMS — Review Queue",
  description: "Internal data-curation interface for the RootsVida Travel Management System",
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
