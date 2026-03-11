import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { Toaster } from "sonner";
import Image from "next/image";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "pAInt-by-numbers",
  description: "Create your very own Paint-by-Numbers canvas",
  icons: {
    icon: "/logo.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <header>
          <div className="flex items-center p-7 gap-x-4">
            <Image
              src="/logo.svg"
              alt="pAInt-by-numbers logo"
              width={60}
              height={60}
            />
            <h1 className="font-paint text-foreground text-5xl font-semibold">
              pAInt-by-numbers
            </h1>
          </div>
          <hr />
        </header>
        {children}
        <Toaster richColors />
      </body>
    </html>
  );
}
