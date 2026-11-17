import type { Metadata } from "next"
import "./globals.css"

export const metadata: Metadata = { title: "Volleyball · Film room" }

export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body>{children}</body>
    </html>
  )
}
