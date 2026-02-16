import type { Metadata } from 'next'
import { Inter, Montserrat, Libre_Baskerville } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/lib/auth-context'

const inter = Inter({ subsets: ['latin'] })
const montserrat = Montserrat({
    subsets: ['latin'],
    variable: '--font-montserrat',
})
const libreBaskerville = Libre_Baskerville({
    weight: ['400', '700'],
    subsets: ['latin'],
    variable: '--font-libre-baskerville',
})

export const metadata: Metadata = {
    title: 'Groundwater Mapper',
    description: 'Professional groundwater mapping and analysis tool',
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en">
            <body className={`${inter.className} ${montserrat.variable} ${libreBaskerville.variable}`}>
                <AuthProvider>
                    {children}
                </AuthProvider>
            </body>
        </html>
    )
}
