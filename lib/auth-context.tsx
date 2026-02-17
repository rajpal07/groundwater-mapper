'use client'

import { createContext, useContext, useEffect, useState, ReactNode } from 'react'
import { User, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged, getAuth } from 'firebase/auth'
import { initializeApp, getApps } from 'firebase/app'
import { firebaseConfig } from './firebase'

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

    useEffect(() => {
        const initAuth = async () => {
            try {
                if (typeof window !== 'undefined') {
                    if (!getApps().length) {
                        initializeApp(firebaseConfig)
                    }
                    const firebaseAuth = getAuth()

                    const unsubscribe = onAuthStateChanged(firebaseAuth, (user) => {
                        setUser(user)
                        setLoading(false)
                    })

                    return () => unsubscribe()
                }
            } catch (error) {
                console.error('Auth init error:', error)
                setLoading(false)
            }
        }

        initAuth()
    }, [])

    const signInWithGoogle = async () => {
        try {
            // Always ensure Firebase is initialized and get fresh auth instance
            if (typeof window !== 'undefined') {
                if (!getApps().length) {
                    initializeApp(firebaseConfig)
                }
                const authInstance = getAuth()
                const provider = new GoogleAuthProvider()
                await signInWithPopup(authInstance, provider)
            } else {
                throw new Error('Cannot sign in on server side')
            }
        } catch (error: any) {
            console.error('Google sign-in error:', error)
            throw error
        }
    }

    const logout = async () => {
        if (typeof window !== 'undefined') {
            const authInstance = getAuth()
            await signOut(authInstance)
        }
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
