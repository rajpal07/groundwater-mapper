'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const { user, loading } = useAuth()
    const router = useRouter()

    useEffect(() => {
        if (!loading && !user) {
            router.push('/auth/signin')
        }
    }, [user, loading, router])

    if (loading) {
        return (
            <div className="loading-screen">
                <div className="spinner"></div>
                <p>Loading...</p>
            </div>
        )
    }

    if (!user) {
        return null
    }

    return (
        <div className="dashboard-layout">
            <header className="dashboard-header">
                <div className="header-content">
                    <a href="/dashboard" className="logo">
                        Groundwater Mapper
                    </a>
                    <nav className="dashboard-nav">
                        <a href="/dashboard/projects">Projects</a>
                        <div className="user-menu">
                            <span className="user-email">{user.email}</span>
                        </div>
                    </nav>
                </div>
            </header>
            <main className="dashboard-main">
                {children}
            </main>
        </div>
    )
}
