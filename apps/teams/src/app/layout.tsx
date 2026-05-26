import type { Metadata } from 'next'
import { Zilla_Slab, Nunito_Sans } from 'next/font/google'
import { Toaster } from 'sonner'
import './globals.css'

const nunito = Nunito_Sans({
  variable: '--font-sans',
  subsets: ['latin'],
  weight: ['300', '400', '600', '700'],
})

const zillaSlab = Zilla_Slab({
  variable: '--font-display',
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
})

export const metadata: Metadata = {
  title: 'Teams · Duendes',
  description: 'Espacio de operaciones interno de Duendes',
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode
}>) {
  return (
    <html lang="es">
      <body
        className={`${nunito.variable} ${zillaSlab.variable} font-sans antialiased`}
      >
        {children}
        <Toaster
          position="bottom-right"
          theme="light"
          toastOptions={{
            style: {
              background: 'hsl(0 0% 100%)',
              border: '1px solid hsl(60 2% 17% / 0.1)',
              color: 'hsl(60 2% 14%)',
            },
          }}
        />
      </body>
    </html>
  )
}
