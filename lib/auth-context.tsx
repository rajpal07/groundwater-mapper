'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { User, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged, getAuth } from 'firebase/auth'

interface AuthContextType {
    user: User | null
    loading: boolean
    signInWithGoogle: () => Promise<void>
    logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
    const [user, setUser] = useState<User | null>(null)
    const [loading, setLoading] = useState(true)
    const [auth, setAuth] = useState<any>(null)

    useEffect(() => {
        const initAuth = async () => {
            try {
                const firebaseAuth = getAuth()
                setAuth(firebaseAuth)

                const unsubscribe = onAuthStateChanged(firebaseAuth, (user) => {
                    setUser(user)
                    setLoading(false)
                })

                return () => unsubscribe()
            } catch (error) {
                console.error('Auth init error:', error)
                setLoading(false)
            }
        }

        initAuth()
    }, [])

    const signInWithGoogle = async () => {
        if (!auth) throw new Error('Auth not initialized')
        const provider = new GoogleAuthProvider()
        await signInWithPopup(auth, provider)
    }

    const logout = async () => {
        if (!auth) throw new Error('Auth not initialized')
        await signOut(auth)
    }

    return (
        <AuthContext.Provider value={{ user, loading, signInWithGoogle, logout }}>
            {children}
        </AuthContext.Provider>
    )
}

export function useAuth() {
    const context = useContext(AuthContext)
    if (context === undefined) {
        throw new Error('useAuth must be used within an AuthProvider')
    }
    return context
}
