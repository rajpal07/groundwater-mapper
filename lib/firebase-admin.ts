import { initializeApp, getApps, cert } from 'firebase-admin/app'
import { getAuth as getAdminAuth } from 'firebase-admin/auth'
import { getFirestore as getAdminFirestore } from 'firebase-admin/firestore'

// For server-side Firebase Admin, we need a service account
let adminDb: ReturnType<typeof getAdminFirestore> | undefined
let adminAuth: ReturnType<typeof getAdminAuth> | undefined

// Check if we're in a server environment
const isServer = typeof window === 'undefined'

console.log('Firebase Admin check - isServer:', isServer)
console.log('Firebase Admin check - FIREBASE_SERVICE_ACCOUNT_KEY exists:', !!process.env.FIREBASE_SERVICE_ACCOUNT_KEY)

if (isServer) {
    const serviceAccountKey = process.env.FIREBASE_SERVICE_ACCOUNT_KEY

    if (serviceAccountKey) {
        try {
            // Parse the service account key from environment variable
            const serviceAccount = JSON.parse(serviceAccountKey)
            console.log('Firebase Admin - Parsed service account, project:', serviceAccount.project_id)

            // Initialize Firebase Admin with service account credentials
            if (!getApps().length) {
                initializeApp({
                    credential: cert(serviceAccount),
                    projectId: serviceAccount.project_id,
                })
                console.log('Firebase Admin initialized successfully')
            } else {
                console.log('Firebase Admin already initialized')
            }

            adminDb = getAdminFirestore()
            adminAuth = getAdminAuth()
            console.log('Firebase Admin DB and Auth initialized')
        } catch (error) {
            console.error('Firebase admin initialization error:', error)
        }
    } else {
        console.log('Firebase Admin - No service account key found in environment')
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
            status: 'pending',
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
        })

    return { id: docRef.id, ...mapData }
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

export async function updateMap(userId: string, projectId: string, mapId: string, mapData: any) {
    if (!adminDb) throw new Error('Firestore not initialized')

    await adminDb
        .collection('users')
        .doc(userId)
        .collection('projects')
        .doc(projectId)
        .collection('maps')
        .doc(mapId)
        .update({
            ...mapData,
            updatedAt: new Date().toISOString(),
        })

    return { id: mapId, ...mapData }
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

