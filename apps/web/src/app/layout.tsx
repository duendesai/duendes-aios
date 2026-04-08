import type { Metadata } from 'next'
import { Geist } from 'next/font/google'
import { Toaster } from 'sonner'
import './globals.css'

const geist = Geist({
  variable: '--font-sans',
  subsets: ['latin'],
})

export const metadata: Metadata = {
  title: 'AIOS',
  description: 'AI Operating System',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="es" className="dark">
      <body className={`${geist.variable} font-sans antialiased`}>
        {children}
        <Toaster
          position="bottom-right"
          theme="dark"
          toastOptions={{
            style: {
              background: 'hsl(224 71% 6%)',
              border: '1px solid hsl(215 28% 17%)',
              color: 'hsl(213 31% 91%)',
            },
          }}
        />
      </body>
    </html>
  )
}
