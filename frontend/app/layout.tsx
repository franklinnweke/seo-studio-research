import type { Metadata } from "next";
import { Providers } from "./providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "seo-studio",
  description: "AI-powered image and website optimization dashboard.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full bg-[#f6f7f9] text-[#151923]">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
