import type { Metadata } from "next";
import { Noto_Sans } from "next/font/google";
import DepthScene from "@/components/DepthScene";
import "./globals.css";

const noto = Noto_Sans({
  variable: "--font-noto",
  subsets: ["latin", "devanagari"],
  weight: ["400", "600", "700"],
});

export const metadata: Metadata = {
  title: "MediKiosk",
  description: "AI clinical history intake — before the consultation",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="hi" className={`${noto.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <DepthScene />
        {children}
      </body>
    </html>
  );
}
