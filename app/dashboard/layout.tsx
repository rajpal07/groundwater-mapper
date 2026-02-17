'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth-context'

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode
}) {
    const { user, loading, logout } = useAuth()
    const router = useRouter()

    useEffect(() => {
        if (!loading && !user) {
            router.push('/auth/signin')
        }
    }, [user, loading, router])

    if (loading) {
        return (
            <div className="flex items-center justify-center min-h-screen">
                <div className="w-10 h-10 border-4 border-gray-200 border-t-primary rounded-full animate-spin"></div>
            </div>
        )
    }

    if (!user) {
        return null
    }

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <header className="bg-white shadow-sm border-b border-gray-200">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                    <div className="flex justify-between items-center h-16">
                        {/* Logo */}
                        <div className="flex-shrink-0">
                            <a href="/dashboard" className="text-xl font-bold text-primary hover:text-primary-dark">
                                Groundwater Mapper
                            </a>
                        </div>

                        {/* Navigation */}
                        <nav className="flex items-center gap-6">
                            <a
                                href="/dashboard/projects"
                                className="text-gray-600 hover:text-primary font-medium transition-colors"
                            >
                                Projects
                            </a>

                            {/* User Menu */}
                            <div className="relative group">
                                <button className="flex items-center gap-2 text-gray-600 hover:text-primary">
                                    {/* User Avatar */}
                                    <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white font-semibold">
                                        {user.email?.charAt(0).toUpperCase()}
                                    </div>
                                    {/* User Name/Email */}
                                    <span className="text-sm font-medium hidden sm:block max-w-[150px] truncate">
                                        {user.email?.split('@')[0]}
                                    </span>
                                </button>

                                {/* Dropdown */}
                                <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                                    <div className="py-2">
                                        <div className="px-4 py-2 text-sm text-gray-500 border-b border-gray-100">
                                            {user.email}
                                        </div>
                                        <button
                                            onClick={() => logout()}
                                            className="w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                                        >
                                            Sign Out
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </nav>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                {children}
            </main>
        </div>
    )
}
