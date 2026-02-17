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
    const [auth, setAuth] = useState<any>(null)

    useEffect(() => {
        const initAuth = async () => {
            try {
                // Initialize Firebase app first if not already initialized
                if (typeof window !== 'undefined') {
                    if (!getApps().length) {
                        initializeApp(firebaseConfig)
                    }
                    const firebaseAuth = getAuth()
                    setAuth(firebaseAuth)

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
        let currentAuth = auth;

        if (!currentAuth) {
            console.log('Auth not initialized, initializing now...');
            // Try to initialize
            if (typeof window !== 'undefined') {
                if (!getApps().length) {
                    initializeApp(firebaseConfig);
                }
                currentAuth = getAuth();
                setAuth(currentAuth);
            }
            if (!currentAuth) throw new Error('Auth not initialized');
        }

        const provider = new GoogleAuthProvider();
        try {
            await signInWithPopup(currentAuth, provider);
        } catch (error: any) {
            console.error('Google sign-in error:', error);
            throw error;
        }
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
