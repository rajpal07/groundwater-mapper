import { initializeApp, getApps, cert, ServiceAccount } from 'firebase-admin/app'
import { getAuth as getAdminAuth } from 'firebase-admin/auth'
import { getFirestore as getAdminFirestore } from 'firebase-admin/firestore'

// For server-side Firebase Admin, we need a service account
// For development, we'll use application default credentials or a simple approach

let adminDb: ReturnType<typeof getAdminFirestore> | undefined

// Check if we're in a server environment
const isServer = typeof window === 'undefined'

if (isServer && process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID) {
    try {
        // Initialize with project ID only - works with Firebase Admin SDK
        initializeApp({
            projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
        })

        adminDb = getAdminFirestore()
    } catch (error) {
        console.error('Firebase admin initialization error:', error)
    }
}

// Verify ID token helper
export async function verifyIdToken(idToken: string): Promise<any> {
    try {
        const auth = getAdminAuth()
        const decodedToken = await auth.verifyIdToken(idToken)
        return decodedToken
    } catch (error) {
        console.error('Token verification error:', error)
        return null
    }
}

// Alias for verifyIdToken
export const verifyFirebaseToken = verifyIdToken

// Firestore helper functions
export async function getUserProjects(userId: string) {
    if (!adminDb) return []

    const snapshot = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .orderBy('createdAt', 'desc')
        .get()

    return snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
    }))
}

export async function createProject(userId: string, projectData: any) {
    if (!adminDb) throw new Error('Firestore not initialized')

    const docRef = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .add({
            ...projectData,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
        })

    return { id: docRef.id, ...projectData }
}

export async function deleteProject(userId: string, projectId: string) {
    if (!adminDb) throw new Error('Firestore not initialized')

    await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .delete()

    const mapsSnapshot = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .collection('maps')
        .get()

    const batch = adminDb.batch()
    mapsSnapshot.docs.forEach(doc => batch.delete(doc.ref))
    await batch.commit()
}

export async function getProjectMaps(userId: string, projectId: string) {
    if (!adminDb) return []

    const snapshot = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .collection('maps')
        .orderBy('createdAt', 'desc')
        .get()

    return snapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
    }))
}

export async function createMap(userId: string, projectId: string, mapData: any) {
    if (!adminDb) throw new Error('Firestore not initialized')

    const docRef = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .collection('maps')
        .add({
            ...mapData,
            createdAt: new Date().toISOString(),
        })

    await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .update({ updatedAt: new Date().toISOString() })

    return { id: docRef.id, ...mapData }
}

export async function deleteMap(userId: string, projectId: string, mapId: string) {
    if (!adminDb) throw new Error('Firestore not initialized')

    await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .collection('maps')
        .doc(mapId)
        .delete()
}

export async function getProject(userId: string, projectId: string) {
    if (!adminDb) return null

    const doc = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .get()

    if (!doc.exists) return null
    return { id: doc.id, ...doc.data() }
}

export async function getProjectWithMaps(userId: string, projectId: string) {
    if (!adminDb) return null

    const projectDoc = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .get()

    if (!projectDoc.exists) return null

    const mapsSnapshot = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .collection('maps')
        .orderBy('createdAt', 'desc')
        .get()

    const maps = mapsSnapshot.docs.map(doc => ({
        id: doc.id,
        ...doc.data()
    }))

    return {
        id: projectDoc.id,
        ...projectDoc.data(),
        maps
    }
}

export async function getMap(userId: string, projectId: string, mapId: string) {
    if (!adminDb) return null

    const doc = await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .collection('maps')
        .doc(mapId)
        .get()

    if (!doc.exists) return null
    return { id: doc.id, ...doc.data() }
}
